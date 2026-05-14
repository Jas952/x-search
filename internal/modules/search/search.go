package search

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"

	"check_x_bot/internal/config"
	"check_x_bot/internal/logging"
)

// searchQueryIDCandidates — hardcoded GraphQL query IDs for SearchTimeline.
// Twitter changes these occasionally; update as needed.
var searchQueryIDCandidates = []string{
	"nK1dw4oV3k4w5TdtcAdSww",
	"gkjsKepM6gl_HmFWoWKfgg",
	"flaR-PUMshxFWZWPNpq4zA",
}

// searchFeatures — standard GraphQL feature flags for SearchTimeline.
var searchFeatures = map[string]any{
	"responsive_web_graphql_exclude_directive_enabled":                        true,
	"verified_phone_label_enabled":                                           false,
	"creator_subscriptions_tweet_preview_api_enabled":                        true,
	"responsive_web_graphql_timeline_navigation_enabled":                     true,
	"responsive_web_graphql_skip_user_profile_image_extensions_enabled":      false,
	"c9s_tweet_anatomy_moderator_badge_enabled":                              true,
	"tweetypie_unmention_optimization_enabled":                               true,
	"responsive_web_edit_tweet_api_enabled":                                  true,
	"graphql_is_translatable_rweb_tweet_is_translatable_enabled":             true,
	"view_counts_everywhere_api_enabled":                                     true,
	"longform_notetweets_consumption_enabled":                                true,
	"responsive_web_twitter_article_tweet_consumption_enabled":               true,
	"tweet_awards_web_tipping_enabled":                                       false,
	"freedom_of_speech_not_reach_fetch_enabled":                              true,
	"standardized_nudges_misinfo":                                            true,
	"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": true,
	"rweb_video_timestamps_enabled":                                          true,
	"longform_notetweets_rich_text_read_enabled":                             true,
	"longform_notetweets_inline_media_enabled":                               true,
	"responsive_web_enhance_cards_enabled":                                   false,
	"responsive_web_media_download_video_enabled":                            true,
	"rweb_lists_timeline_redesign_enabled":                                   true,
	"communities_web_enable_tweet_community_results_fetch":                   true,
	"articles_preview_enabled":                                               true,
	"rweb_tipjar_consumption_enabled":                                        true,
	"creator_subscriptions_quote_tweet_preview_enabled":                      false,
}

// package-level state: remembers which HTTP method worked last.
var lastWorkingMethod string // "post_body", "get_params", "post_params"

// working query ID index
var workingQueryIDIdx int

// ---------------------------------------------------------------------------
// HTTP request methods (3 fallback strategies, like Python)
// ---------------------------------------------------------------------------

func tryPostBody(ctx context.Context, client *http.Client, urlStr string, variables map[string]any, headers, cookies map[string]any) (*http.Response, error) {
	payload := map[string]any{
		"variables": variables,
		"features":  searchFeatures,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, urlStr, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	applyHeadersAndCookies(req, headers, cookies)
	req.Header.Set("content-type", "application/json")
	return client.Do(req)
}

func tryGetParams(ctx context.Context, client *http.Client, urlStr string, variables map[string]any, headers, cookies map[string]any) (*http.Response, error) {
	varsJSON, _ := json.Marshal(variables)
	featJSON, _ := json.Marshal(searchFeatures)

	u, err := url.Parse(urlStr)
	if err != nil {
		return nil, err
	}
	q := u.Query()
	q.Set("variables", string(varsJSON))
	q.Set("features", string(featJSON))
	u.RawQuery = q.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return nil, err
	}
	applyHeadersAndCookies(req, headers, cookies)
	return client.Do(req)
}

func tryPostParams(ctx context.Context, client *http.Client, urlStr string, variables map[string]any, headers, cookies map[string]any) (*http.Response, error) {
	varsJSON, _ := json.Marshal(variables)
	featJSON, _ := json.Marshal(searchFeatures)

	u, err := url.Parse(urlStr)
	if err != nil {
		return nil, err
	}
	q := u.Query()
	q.Set("variables", string(varsJSON))
	q.Set("features", string(featJSON))
	u.RawQuery = q.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, u.String(), nil)
	if err != nil {
		return nil, err
	}
	applyHeadersAndCookies(req, headers, cookies)
	return client.Do(req)
}

type methodFunc func(ctx context.Context, client *http.Client, urlStr string, variables map[string]any, headers, cookies map[string]any) (*http.Response, error)

type requestMethod struct {
	name string
	fn   methodFunc
}

var allMethods = []requestMethod{
	{"post_body", tryPostBody},
	{"get_params", tryGetParams},
	{"post_params", tryPostParams},
}

// rawSearchRequest tries all 3 HTTP methods with fallback.
// Handles 429 (rate limit) and 400/404 (wrong method → try next).
func rawSearchRequest(ctx context.Context, client *http.Client, cfg *config.Config, urlStr string, variables map[string]any) (map[string]any, error) {
	headers := cfg.HeadersSearch()
	cookies := cfg.CookiesSearch()

	// order methods: last working first
	ordered := make([]requestMethod, 0, len(allMethods))
	if lastWorkingMethod != "" {
		for _, m := range allMethods {
			if m.name == lastWorkingMethod {
				ordered = append(ordered, m)
				break
			}
		}
	}
	for _, m := range allMethods {
		if m.name != lastWorkingMethod {
			ordered = append(ordered, m)
		}
	}

	for _, method := range ordered {
		reqCtx, cancel := context.WithTimeout(ctx, cfg.HTTPTimeout)
		resp, err := method.fn(reqCtx, client, urlStr, variables, headers, cookies)
		cancel()

		if err != nil {
			logging.LogDebug("search method failed",
				logging.String("method", method.name),
				logging.Err(err))
			continue
		}

		body, _ := io.ReadAll(resp.Body)
		_ = resp.Body.Close()

		switch resp.StatusCode {
		case http.StatusOK:
			lastWorkingMethod = method.name
			var result map[string]any
			if err := json.Unmarshal(body, &result); err != nil {
				return nil, fmt.Errorf("json decode error: %w", err)
			}
			return result, nil

		case http.StatusTooManyRequests:
			resetStr := resp.Header.Get("x-rate-limit-reset")
			wait := 30 // default wait
			if resetStr != "" {
				if resetTS, err := strconv.ParseInt(resetStr, 10, 64); err == nil {
					wait = int(resetTS - time.Now().Unix() + 1)
					if wait < 5 {
						wait = 5
					}
					if wait > 120 {
						wait = 120
					}
				}
			}
			logging.LogWarn("Rate limited, sleeping",
				logging.Int("seconds", wait))
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(time.Duration(wait) * time.Second):
			}
			// retry once after rate limit
			return rawSearchRequest(ctx, client, cfg, urlStr, variables)

		case http.StatusBadRequest, http.StatusNotFound:
			logging.LogDebug("search method returned error status, trying next",
				logging.String("method", method.name),
				logging.Int("status", resp.StatusCode))
			continue

		default:
			snippet := string(body)
			if len(snippet) > 300 {
				snippet = snippet[:300]
			}
			logging.LogError("SearchTimeline unexpected status",
				logging.Int("status", resp.StatusCode),
				logging.String("body", snippet))
			return nil, fmt.Errorf("SearchTimeline status %d", resp.StatusCode)
		}
	}

	return nil, fmt.Errorf("all SearchTimeline methods failed")
}

// ---------------------------------------------------------------------------
// Search — main search function
// ---------------------------------------------------------------------------

// Search performs a SearchTimeline GraphQL query with pagination.
func Search(ctx context.Context, client *http.Client, cfg *config.Config, query string, pages, countPerPage int, sortOrder string) ([]TweetData, error) {
	if pages <= 0 {
		pages = 1
	}
	if countPerPage <= 0 {
		countPerPage = 20
	}

	product := "Top"
	if sortOrder == "latest" || sortOrder == "recency" {
		product = "Latest"
	}

	queryID := searchQueryIDCandidates[workingQueryIDIdx]
	urlStr := fmt.Sprintf("https://x.com/i/api/graphql/%s/SearchTimeline", queryID)

	variables := map[string]any{
		"rawQuery":    query,
		"count":       countPerPage,
		"querySource": "typed_query",
		"product":     product,
	}

	var allTweets []TweetData

	for page := range pages {
		data, err := rawSearchRequest(ctx, client, cfg, urlStr, variables)

		// if failed, try next query ID candidate
		if err != nil && page == 0 {
			for i := range searchQueryIDCandidates {
				nextIdx := (workingQueryIDIdx + i + 1) % len(searchQueryIDCandidates)
				if nextIdx == workingQueryIDIdx {
					continue
				}
				logging.LogWarn("Trying next query ID candidate",
					logging.String("queryID", searchQueryIDCandidates[nextIdx]))
				queryID = searchQueryIDCandidates[nextIdx]
				urlStr = fmt.Sprintf("https://x.com/i/api/graphql/%s/SearchTimeline", queryID)
				data, err = rawSearchRequest(ctx, client, cfg, urlStr, variables)
				if err == nil {
					workingQueryIDIdx = nextIdx
					break
				}
			}
		}

		if err != nil {
			return allTweets, fmt.Errorf("search failed on page %d: %w", page, err)
		}

		tweets := extractTweetsFromTimeline(data)
		allTweets = append(allTweets, tweets...)

		if page < pages-1 {
			cursor := getNextCursor(data)
			if cursor == "" {
				break
			}
			variables["cursor"] = cursor

			select {
			case <-ctx.Done():
				return allTweets, ctx.Err()
			case <-time.After(500 * time.Millisecond):
			}
		}
	}

	return allTweets, nil
}

// ---------------------------------------------------------------------------
// Response parsing
// ---------------------------------------------------------------------------

func extractTweetsFromTimeline(data map[string]any) []TweetData {
	var tweets []TweetData

	dataObj, _ := data["data"].(map[string]any)
	if dataObj == nil {
		return tweets
	}
	searchByRaw, _ := dataObj["search_by_raw_query"].(map[string]any)
	if searchByRaw == nil {
		return tweets
	}
	searchTimeline, _ := searchByRaw["search_timeline"].(map[string]any)
	if searchTimeline == nil {
		return tweets
	}
	timeline, _ := searchTimeline["timeline"].(map[string]any)
	if timeline == nil {
		return tweets
	}
	instructions, _ := timeline["instructions"].([]any)

	for _, instrRaw := range instructions {
		instr, _ := instrRaw.(map[string]any)
		if instr == nil {
			continue
		}
		entries, _ := instr["entries"].([]any)
		for _, entryRaw := range entries {
			entry, _ := entryRaw.(map[string]any)
			if entry == nil {
				continue
			}
			content, _ := entry["content"].(map[string]any)
			if content == nil {
				continue
			}
			itemContent, _ := content["itemContent"].(map[string]any)
			if itemContent == nil {
				continue
			}
			tweetResults, _ := itemContent["tweet_results"].(map[string]any)
			if tweetResults == nil {
				continue
			}
			result, _ := tweetResults["result"].(map[string]any)
			if result == nil {
				continue
			}
			td := parseTweetFromResult(result)
			if td != nil {
				tweets = append(tweets, *td)
			}
		}
	}
	return tweets
}

func parseTweetFromResult(result map[string]any) *TweetData {
	tweetData := result
	// handle "tweet" wrapper
	if inner, ok := result["tweet"].(map[string]any); ok {
		tweetData = inner
	}

	core, _ := tweetData["core"].(map[string]any)
	userResults, _ := getNestedMap(core, "user_results", "result")
	legacyUser, _ := userResults["legacy"].(map[string]any)
	legacyTweet, _ := tweetData["legacy"].(map[string]any)

	if legacyTweet == nil {
		return nil
	}

	tweetID := getString(legacyTweet, "id_str")
	if tweetID == "" {
		tweetID = getString(tweetData, "rest_id")
	}
	if tweetID == "" {
		return nil
	}

	text := getString(legacyTweet, "full_text")
	if text == "" {
		text = getString(legacyTweet, "text")
	}

	username := getString(legacyUser, "screen_name")
	if username == "" {
		username = "?"
	}
	name := getString(legacyUser, "name")
	if name == "" {
		name = "?"
	}
	authorID := getString(legacyTweet, "user_id_str")
	if authorID == "" {
		authorID = getString(userResults, "rest_id")
	}

	createdAt := getString(legacyTweet, "created_at")
	conversationID := getString(legacyTweet, "conversation_id_str")
	if conversationID == "" {
		conversationID = tweetID
	}

	metrics := TweetMetrics{
		Likes:    getInt(legacyTweet, "favorite_count"),
		Retweets: getInt(legacyTweet, "retweet_count"),
		Replies:  getInt(legacyTweet, "reply_count"),
		Quotes:   getInt(legacyTweet, "quote_count"),
		Bookmarks: getInt(legacyTweet, "bookmark_count"),
	}

	// impressions from views.count
	if views, _ := tweetData["views"].(map[string]any); views != nil {
		if countStr, ok := views["count"].(string); ok {
			if n, err := strconv.Atoi(countStr); err == nil {
				metrics.Impressions = n
			}
		} else if countNum, ok := views["count"].(float64); ok {
			metrics.Impressions = int(countNum)
		}
	}

	// URLs
	var urls []string
	entities, _ := legacyTweet["entities"].(map[string]any)
	if entities != nil {
		if urlList, ok := entities["urls"].([]any); ok {
			for _, uRaw := range urlList {
				u, _ := uRaw.(map[string]any)
				expanded := getString(u, "expanded_url")
				if expanded == "" {
					expanded = getString(u, "url")
				}
				if expanded != "" {
					urls = append(urls, expanded)
				}
			}
		}
	}

	// Hashtags
	var hashtags []string
	if entities != nil {
		if hashList, ok := entities["hashtags"].([]any); ok {
			for _, hRaw := range hashList {
				h, _ := hRaw.(map[string]any)
				if t := getString(h, "text"); t != "" {
					hashtags = append(hashtags, t)
				}
			}
		}
	}

	// Mentions
	var mentions []string
	if entities != nil {
		if mentionList, ok := entities["user_mentions"].([]any); ok {
			for _, mRaw := range mentionList {
				m, _ := mRaw.(map[string]any)
				if sn := getString(m, "screen_name"); sn != "" {
					mentions = append(mentions, sn)
				}
			}
		}
	}

	return &TweetData{
		ID:             tweetID,
		Text:           text,
		AuthorID:       authorID,
		Username:       username,
		Name:           name,
		CreatedAt:      createdAt,
		ConversationID: conversationID,
		Metrics:        metrics,
		URLs:           urls,
		Mentions:       mentions,
		Hashtags:       hashtags,
		TweetURL:       fmt.Sprintf("https://x.com/%s/status/%s", username, tweetID),
	}
}

func getNextCursor(data map[string]any) string {
	dataObj, _ := data["data"].(map[string]any)
	if dataObj == nil {
		return ""
	}
	searchByRaw, _ := dataObj["search_by_raw_query"].(map[string]any)
	if searchByRaw == nil {
		return ""
	}
	searchTimeline, _ := searchByRaw["search_timeline"].(map[string]any)
	if searchTimeline == nil {
		return ""
	}
	timeline, _ := searchTimeline["timeline"].(map[string]any)
	if timeline == nil {
		return ""
	}
	instructions, _ := timeline["instructions"].([]any)

	for _, instrRaw := range instructions {
		instr, _ := instrRaw.(map[string]any)
		if instr == nil {
			continue
		}
		entries, _ := instr["entries"].([]any)
		for _, entryRaw := range entries {
			entry, _ := entryRaw.(map[string]any)
			if entry == nil {
				continue
			}
			entryID := getString(entry, "entryId")
			if strings.HasPrefix(entryID, "cursor-bottom") {
				content, _ := entry["content"].(map[string]any)
				if content != nil {
					return getString(content, "value")
				}
			}
		}
	}
	return ""
}

// ---------------------------------------------------------------------------
// Filtering & dedup
// ---------------------------------------------------------------------------

// FilterEngagement returns tweets meeting minimum engagement thresholds.
func FilterEngagement(tweets []TweetData, minLikes, minImpressions int) []TweetData {
	if minLikes <= 0 && minImpressions <= 0 {
		return tweets
	}
	var result []TweetData
	for _, t := range tweets {
		if t.Metrics.Likes >= minLikes && t.Metrics.Impressions >= minImpressions {
			result = append(result, t)
		}
	}
	return result
}

// Dedupe removes duplicate tweets by ID.
func Dedupe(tweets []TweetData) []TweetData {
	seen := make(map[string]struct{}, len(tweets))
	var result []TweetData
	for _, t := range tweets {
		if _, ok := seen[t.ID]; ok {
			continue
		}
		seen[t.ID] = struct{}{}
		result = append(result, t)
	}
	return result
}

// SortByLikes sorts tweets by likes in descending order.
func SortByLikes(tweets []TweetData) {
	sort.Slice(tweets, func(i, j int) bool {
		return tweets[i].Metrics.Likes > tweets[j].Metrics.Likes
	})
}

// ---------------------------------------------------------------------------
// Helpers (same pattern as new_subs)
// ---------------------------------------------------------------------------

func applyHeadersAndCookies(req *http.Request, headers, cookies map[string]any) {
	for k, v := range headers {
		req.Header.Set(k, fmt.Sprint(v))
	}
	if len(cookies) == 0 {
		return
	}
	var parts []string
	for k, v := range cookies {
		parts = append(parts, fmt.Sprintf("%s=%v", k, v))
	}
	req.Header.Set("Cookie", strings.Join(parts, "; "))
}

func getString(m map[string]any, key string) string {
	if m == nil {
		return ""
	}
	v, _ := m[key].(string)
	return v
}

func getInt(m map[string]any, key string) int {
	if m == nil {
		return 0
	}
	switch v := m[key].(type) {
	case float64:
		return int(v)
	case int:
		return v
	case string:
		n, _ := strconv.Atoi(v)
		return n
	default:
		return 0
	}
}

func getNestedMap(m map[string]any, keys ...string) (map[string]any, bool) {
	current := m
	for _, k := range keys {
		if current == nil {
			return nil, false
		}
		next, ok := current[k].(map[string]any)
		if !ok {
			return nil, false
		}
		current = next
	}
	return current, true
}
