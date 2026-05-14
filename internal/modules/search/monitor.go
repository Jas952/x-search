package search

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand/v2"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"check_x_bot/internal/config"
	"check_x_bot/internal/logging"
	"check_x_bot/internal/telegram"
)

const (
	baseDir          = "modules/search"
	configFile       = "modules/search/monitor_config.json"
	defaultSeenFile  = "modules/search/seen_tweets.json"
	defaultReportDir = "modules/search/reports"
)

// LoadMonitorConfig reads the monitor config from disk.
func LoadMonitorConfig() (*MonitorConfig, error) {
	data, err := os.ReadFile(configFile)
	if err != nil {
		return nil, fmt.Errorf("read monitor config: %w", err)
	}
	var mc MonitorConfig
	if err := json.Unmarshal(data, &mc); err != nil {
		return nil, fmt.Errorf("parse monitor config: %w", err)
	}
	// defaults
	if mc.Settings.CycleIntervalMinutes <= 0 {
		mc.Settings.CycleIntervalMinutes = 10
	}
	if mc.Settings.QueriesPerCycle <= 0 {
		mc.Settings.QueriesPerCycle = 3
	}
	if mc.Settings.PagesPerQuery <= 0 {
		mc.Settings.PagesPerQuery = 1
	}
	if mc.Settings.ResultsPerQuery <= 0 {
		mc.Settings.ResultsPerQuery = 20
	}
	if mc.Settings.PauseBetweenQueriesSec <= 0 {
		mc.Settings.PauseBetweenQueriesSec = 15
	}
	if mc.Settings.SeenTweetsFile == "" {
		mc.Settings.SeenTweetsFile = defaultSeenFile
	}
	if mc.Settings.MaxSeenTweets <= 0 {
		mc.Settings.MaxSeenTweets = 50_000
	}
	if mc.Settings.ReportDir == "" {
		mc.Settings.ReportDir = defaultReportDir
	}
	return &mc, nil
}

// RunMonitorCycle executes one monitoring cycle:
// select queries by priority, search, filter, send to Telegram, save report.
func RunMonitorCycle(ctx context.Context, cfg *config.Config, tg *telegram.Client) error {
	mc, err := LoadMonitorConfig()
	if err != nil {
		return err
	}

	seen := NewSeenTracker(mc.Settings.SeenTweetsFile, mc.Settings.MaxSeenTweets)
	if err := seen.Load(); err != nil {
		logging.LogWarn("Failed to load seen tracker, starting fresh", logging.Err(err))
	}

	client := &http.Client{Timeout: cfg.HTTPTimeout}

	// select queries by priority
	queries := selectQueriesByPriority(mc.Queries, mc.Settings.QueriesPerCycle)

	logging.LogInfo("Search monitor cycle starting",
		logging.Int("queries", len(queries)),
		logging.Int("seen_count", seen.Count()))

	totalNew := 0

	for i, qCfg := range queries {
		select {
		case <-ctx.Done():
			_ = seen.Save()
			return ctx.Err()
		default:
		}

		newCount, err := runSingleQuery(ctx, client, cfg, tg, qCfg, seen, mc.Settings)
		if err != nil {
			logging.LogError("Search query failed",
				logging.String("name", qCfg.Name),
				logging.Err(err))
		}
		totalNew += newCount

		// pause between queries with jitter
		if i < len(queries)-1 {
			jitter := 0.5 + rand.Float64() // 0.5 to 1.5
			wait := time.Duration(float64(mc.Settings.PauseBetweenQueriesSec)*jitter) * time.Second
			select {
			case <-ctx.Done():
				_ = seen.Save()
				return ctx.Err()
			case <-time.After(wait):
			}
		}
	}

	if err := seen.Save(); err != nil {
		logging.LogError("Failed to save seen tracker", logging.Err(err))
	}

	logging.LogInfo("Search monitor cycle completed",
		logging.Int("total_new", totalNew),
		logging.Int("seen_count", seen.Count()))

	return nil
}

func runSingleQuery(
	ctx context.Context,
	client *http.Client,
	cfg *config.Config,
	tg *telegram.Client,
	qCfg QueryConfig,
	seen *SeenTracker,
	settings MonitorSettings,
) (int, error) {
	logging.LogInfo("Searching", logging.String("name", qCfg.Name))

	sortOrder := "latest"
	if qCfg.Sort == "top" || qCfg.Sort == "relevancy" {
		sortOrder = "relevancy"
	}

	// check cache first
	cacheParams := fmt.Sprintf("%s|%d|%s", qCfg.Sort, settings.PagesPerQuery, qCfg.Query)
	if cached, ok := CacheGet(qCfg.Query, cacheParams, 0); ok {
		logging.LogDebug("Cache hit", logging.String("query", qCfg.Name))
		newTweets := processResults(cached, qCfg, seen)
		if len(newTweets) > 0 {
			sendToTelegram(ctx, tg, qCfg, newTweets)
			saveReport(qCfg, newTweets, settings)
		}
		return len(newTweets), nil
	}

	tweets, err := Search(ctx, client, cfg, qCfg.Query, settings.PagesPerQuery, settings.ResultsPerQuery, sortOrder)
	if err != nil {
		return 0, err
	}

	// cache results
	CacheSet(qCfg.Query, cacheParams, tweets)

	newTweets := processResults(tweets, qCfg, seen)

	if len(newTweets) > 0 {
		sendToTelegram(ctx, tg, qCfg, newTweets)
		saveReport(qCfg, newTweets, settings)
		logging.LogInfo("New tweets found",
			logging.String("name", qCfg.Name),
			logging.Int("new", len(newTweets)),
			logging.Int("total", len(tweets)))
	} else {
		logging.LogInfo("No new tweets",
			logging.String("name", qCfg.Name),
			logging.Int("total", len(tweets)))
	}

	return len(newTweets), nil
}

func processResults(tweets []TweetData, qCfg QueryConfig, seen *SeenTracker) []TweetData {
	// engagement filter
	if qCfg.MinLikes > 0 {
		tweets = FilterEngagement(tweets, qCfg.MinLikes, 0)
	}

	// dedupe
	tweets = Dedupe(tweets)

	// filter already seen
	newTweets := seen.FilterNew(tweets)

	// sort by likes
	SortByLikes(newTweets)

	return newTweets
}

func sendToTelegram(ctx context.Context, tg *telegram.Client, qCfg QueryConfig, tweets []TweetData) {
	msg := FormatResultsTelegram(tweets, qCfg.Name, 15)
	if err := tg.SendMessage(ctx, msg); err != nil {
		logging.LogError("Failed to send search results to Telegram", logging.Err(err))
	}
}

func saveReport(qCfg QueryConfig, tweets []TweetData, settings MonitorSettings) {
	if !settings.SaveReports {
		return
	}
	reportDir := settings.ReportDir
	_ = os.MkdirAll(reportDir, 0o755)

	date := time.Now().Format("2006-01-02")
	filename := filepath.Join(reportDir, fmt.Sprintf("report-%s.md", date))

	now := time.Now().Format("15:04:05")
	var section string
	section += fmt.Sprintf("\n## [%s] %s\n", now, qCfg.Name)
	section += fmt.Sprintf("Query: `%s`\n", qCfg.Query)
	section += fmt.Sprintf("New tweets: %d\n\n", len(tweets))

	for _, t := range tweets {
		section += FormatTweetMarkdown(t) + "\n\n"
	}
	section += "---\n"

	// create header if file is new
	if _, err := os.Stat(filename); os.IsNotExist(err) {
		header := fmt.Sprintf("# Twitter Auto-Monitor Report — %s\n\n---\n", date)
		_ = os.WriteFile(filename, []byte(header), 0o644)
	}

	f, err := os.OpenFile(filename, os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	defer func() { _ = f.Close() }()
	_, _ = f.WriteString(section)
}

// selectQueriesByPriority picks queries for this cycle: high first, then medium, then low.
// Shuffles within each priority group.
func selectQueriesByPriority(queries []QueryConfig, limit int) []QueryConfig {
	var high, medium, low []QueryConfig
	for _, q := range queries {
		switch q.Priority {
		case "high":
			high = append(high, q)
		case "medium":
			medium = append(medium, q)
		default:
			low = append(low, q)
		}
	}

	shuffle := func(s []QueryConfig) {
		rand.Shuffle(len(s), func(i, j int) { s[i], s[j] = s[j], s[i] })
	}
	shuffle(high)
	shuffle(medium)
	shuffle(low)

	ordered := make([]QueryConfig, 0, len(queries))
	ordered = append(ordered, high...)
	ordered = append(ordered, medium...)
	ordered = append(ordered, low...)

	if len(ordered) > limit {
		ordered = ordered[:limit]
	}
	return ordered
}
