package new_subs

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"check_x_bot/internal/config"
	"check_x_bot/internal/logging"
	"check_x_bot/internal/telegram"
)

const (
	baseDir      = "modules/new_subs"
	targetsFile  = "targets.txt"
	sleepBetween = time.Second
)

const (
	userByScreenNameURL = "https://x.com/i/api/graphql/x3RLKWW1Tl7JgU7YtGxuzw/UserByScreenName"
	followingURL        = "https://x.com/i/api/graphql/uAvNrZNqQfWpTerfEDd4DA/Following"
	oldDirName          = "old"
	newDirName          = "new"
)

// ScanAndUpdateSubscriptions:
// 1) Получает свежий список подписок из Twitter для каждого таргета.
// 2) Сравнивает с old_{nickname}.json в modules/new_subs/old.
// 3) Записывает только новые подписки в new/new_{nickname}.json.
// 4) Обновляет old_{nickname}.json актуальными данными.
func ScanAndUpdateSubscriptions(ctx context.Context, cfg *config.Config) error {
	logging.LogInfo("new_subs: starting scan & update")

	targetsMap, err := loadTargets()
	if err != nil {
		return fmt.Errorf("scan: load targets: %w", err)
	}
	if len(targetsMap) == 0 {
		logging.LogWarn("new_subs: no targets in targets.txt, skipping scan")
		return nil
	}

	if err := os.MkdirAll(filepath.Join(baseDir, oldDirName), 0o755); err != nil {
		return fmt.Errorf("scan: create old dir: %w", err)
	}
	if err := os.MkdirAll(filepath.Join(baseDir, newDirName), 0o755); err != nil {
		return fmt.Errorf("scan: create new dir: %w", err)
	}

	client := &http.Client{
		Timeout: cfg.HTTPTimeout,
	}

	for nickname := range targetsMap {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		logging.LogInfo("new_subs: scanning followings for target",
			logging.String("username", nickname),
		)

		userID, err := getUserID(ctx, client, cfg, nickname)
		if err != nil || userID == "" {
			logging.LogError("new_subs: failed to get user id",
				logging.String("username", nickname),
				logging.Err(err),
			)
			continue
		}

		current, err := getFollowings(ctx, client, cfg, userID, nickname)
		if err != nil {
			logging.LogError("new_subs: failed to get followings",
				logging.String("username", nickname),
				logging.Err(err),
			)
			continue
		}
		if len(current) == 0 {
			logging.LogWarn("new_subs: empty followings list",
				logging.String("username", nickname),
			)
			continue
		}

		oldPath := filepath.Join(baseDir, oldDirName, fmt.Sprintf("old_%s.json", nickname))
		oldRaw, err := loadRawList(oldPath)
		if err != nil {
			logging.LogError("new_subs: failed to load old followings",
				logging.String("file", oldPath),
				logging.Err(err),
			)
			// продолжаем как с первым запуском
			oldRaw = nil
		}

		// Первый запуск: сохраняем базовую линию (как множество всех уже виденных),
		// new_* делаем пустым и НИЧЕГО не отправляем.
		if len(oldRaw) == 0 {
			merged := mergeRawLists(nil, current)
			if err := saveRawList(oldPath, merged); err != nil {
				logging.LogError("new_subs: failed to save baseline followings",
					logging.String("file", oldPath),
					logging.Err(err),
				)
				continue
			}

			newPath := filepath.Join(baseDir, newDirName, fmt.Sprintf("new_%s.json", nickname))
			if err := saveRawList(newPath, [][]any{}); err != nil {
				logging.LogWarn("new_subs: failed to init empty new_* file",
					logging.String("file", newPath),
					logging.Err(err),
				)
			}

			logging.LogSuccess("new_subs: baseline followings saved (first run, nothing sent)",
				logging.String("username", nickname),
				logging.Int("count", len(current)),
			)
			continue
		}

		// Находим новые подписки по username (индекс 2 в массиве)
		newOnly := diffByUsername(oldRaw, current)

		newPath := filepath.Join(baseDir, newDirName, fmt.Sprintf("new_%s.json", nickname))
		if len(newOnly) > 0 {
			if err := saveRawList(newPath, newOnly); err != nil {
				logging.LogError("new_subs: failed to save new followings",
					logging.String("file", newPath),
					logging.Err(err),
				)
			} else {
				logging.LogSuccess("new_subs: new followings detected",
					logging.String("username", nickname),
					logging.Int("count", len(newOnly)),
				)
			}
		} else {
			// Если новых нет — просто оставляем пустой JSON-файл new_*.json
			if err := saveRawList(newPath, [][]any{}); err != nil {
				logging.LogWarn("new_subs: failed to save empty new_* file",
					logging.String("file", newPath),
					logging.Err(err),
				)
			}
			logging.LogInfo("new_subs: no new followings for user",
				logging.String("username", nickname),
			)
		}

		// Обновляем baseline как множество всех уже виденных подписчиков (union).
		updatedOld := mergeRawLists(oldRaw, newOnly)
		if err := saveRawList(oldPath, updatedOld); err != nil {
			logging.LogError("new_subs: failed to update baseline followings",
				logging.String("file", oldPath),
				logging.Err(err),
			)
		}
	}

	return nil
}

// ProcessNewSubscriptions обрабатывает новые подписки и отправляет их в Telegram.
// Логика максимально близка к старому Python-модулю, но работает только с Telegram.
func ProcessNewSubscriptions(ctx context.Context, cfg *config.Config, tg *telegram.Client) error {
	logging.LogInfo("Starting new_subs processing...")

	targets, err := loadTargets()
	if err != nil {
		return fmt.Errorf("load targets: %w", err)
	}
	if len(targets) == 0 {
		logging.LogWarn("No targets in new_subs/targets.txt – nothing to do")
		return nil
	}

	var total int

	for nickname := range targets {
		filePath := filepath.Join(baseDir, "new", fmt.Sprintf("new_%s.json", nickname))

		f, err := os.Open(filePath)
		if err != nil {
			if os.IsNotExist(err) {
				logging.LogDebug("No new subscriptions file for target",
					logging.String("target", nickname),
				)
				continue
			}
			return fmt.Errorf("open new file for %s: %w", nickname, err)
		}
		var users [][]any
		if err := json.NewDecoder(f).Decode(&users); err != nil {
			_ = f.Close()
			logging.LogWarn("Failed to decode subscriptions file",
				logging.String("file", filePath),
				logging.Err(err),
			)
			continue
		}
		_ = f.Close()

		foundBy := nickname

		logging.LogInfo("Processing subscriptions file",
			logging.String("file", filePath),
			logging.String("found_by", foundBy),
		)

		for i, user := range users {
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
			}

			sub, err := parseUser(user)
			if err != nil {
				logging.LogWarn("Failed to parse subscription user",
					logging.Int("index", i),
					logging.Err(err),
				)
				continue
			}

			caption := buildCaption(foundBy, sub)

			var photoURL string
			if sub.BannerURL != "" {
				photoURL = sub.BannerURL
			} else if sub.AvatarURL != "" {
				photoURL = sub.AvatarURL
			}

			if photoURL == "" {
				logging.LogWarn("No avatar or banner for user, skipping",
					logging.String("username", sub.Username),
				)
				continue
			}

			if err := tg.SendPhoto(ctx, photoURL, caption); err != nil {
				logging.LogError("Failed to send subscription to Telegram",
					logging.String("username", sub.Username),
					logging.Err(err),
				)
				continue
			}

			logging.LogSuccess("Subscription sent to Telegram",
				logging.String("username", sub.Username),
				logging.String("found_by", foundBy),
			)
			total++

			time.Sleep(sleepBetween)
		}
	}

	if total == 0 {
		logging.LogInfo("No subscriptions sent in this cycle")
	} else {
		logging.LogSuccess(fmt.Sprintf("Processed %d subscriptions", total))
	}

	return nil
}

func loadTargets() (map[string]struct{}, error) {
	path := filepath.Join(baseDir, targetsFile)

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return map[string]struct{}{}, nil
		}
		return nil, err
	}

	lines := strings.Split(string(data), "\n")
	targets := make(map[string]struct{})
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		line = strings.TrimPrefix(line, "@")
		targets[line] = struct{}{}
	}
	return targets, nil
}

// SyncFilesWithTargets удаляет старые файлы old_*/new_* для никнеймов,
// которых больше нет в targets.txt. Вызывается при старте бота.
func SyncFilesWithTargets() error {
	targetsMap, err := loadTargets()
	if err != nil {
		return err
	}

	oldDir := filepath.Join(baseDir, oldDirName)
	newDir := filepath.Join(baseDir, newDirName)

	_ = os.MkdirAll(oldDir, 0o755)
	_ = os.MkdirAll(newDir, 0o755)

	// чистим old_*.json
	if entries, err := os.ReadDir(oldDir); err == nil {
		for _, e := range entries {
			if e.IsDir() {
				continue
			}
			name := e.Name()
			if !strings.HasPrefix(name, "old_") || !strings.HasSuffix(name, ".json") {
				continue
			}
			nickname := strings.TrimSuffix(strings.TrimPrefix(name, "old_"), ".json")
			if _, ok := targetsMap[nickname]; !ok {
				path := filepath.Join(oldDir, name)
				if err := os.Remove(path); err == nil {
					logging.LogInfo("new_subs: removed old_* file for non-target user",
						logging.String("file", path),
					)
				}
			}
		}
	}

	// чистим new_*.json
	if entries, err := os.ReadDir(newDir); err == nil {
		for _, e := range entries {
			if e.IsDir() {
				continue
			}
			name := e.Name()
			if !strings.HasPrefix(name, "new_") || !strings.HasSuffix(name, ".json") {
				continue
			}
			nickname := strings.TrimSuffix(strings.TrimPrefix(name, "new_"), ".json")
			if _, ok := targetsMap[nickname]; !ok {
				path := filepath.Join(newDir, name)
				if err := os.Remove(path); err == nil {
					logging.LogInfo("new_subs: removed new_* file for non-target user",
						logging.String("file", path),
					)
				}
			}
		}
	}

	return nil
}

// ---------- Работа с Twitter (ID + подписки) ----------

func getUserID(ctx context.Context, client *http.Client, cfg *config.Config, screenName string) (string, error) {
	cookies := cfg.TwitterCookies()
	headers := cfg.HeadersID()
	params := cfg.ParamsID()

	reqCtx, cancel := context.WithTimeout(ctx, cfg.HTTPTimeout)
	defer cancel()

	req, err := http.NewRequestWithContext(reqCtx, http.MethodGet, userByScreenNameURL, nil)
	if err != nil {
		return "", err
	}

	applyHeadersAndCookies(req, headers, cookies)
	req.Header.Set("referer", fmt.Sprintf("https://x.com/%s/following", screenName))

	q := buildQuery(params)
	variables := map[string]any{"screen_name": screenName}
	b, _ := json.Marshal(variables)
	q.Set("variables", string(b))
	req.URL.RawQuery = q.Encode()

	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer func() {
		_ = resp.Body.Close()
	}()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("unexpected status %d", resp.StatusCode)
	}

	var body map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return "", err
	}

	data, _ := body["data"].(map[string]any)
	if data == nil {
		return "", fmt.Errorf("no data in response")
	}
	user, _ := data["user"].(map[string]any)
	if user == nil {
		return "", fmt.Errorf("no user in response")
	}
	result, _ := user["result"].(map[string]any)
	if result == nil {
		return "", fmt.Errorf("no result in response")
	}
	restID, _ := result["rest_id"].(string)
	if restID == "" {
		return "", fmt.Errorf("rest_id not found")
	}
	return restID, nil
}

func getFollowings(ctx context.Context, client *http.Client, cfg *config.Config, userID, screenName string) ([][]any, error) {
	cookies := cfg.CookiesFollowing()
	headers := cfg.HeadersFollowing()
	params := cfg.ParamsFollowing()

	reqCtx, cancel := context.WithTimeout(ctx, cfg.HTTPTimeout)
	defer cancel()

	req, err := http.NewRequestWithContext(reqCtx, http.MethodGet, followingURL, nil)
	if err != nil {
		return nil, err
	}

	applyHeadersAndCookies(req, headers, cookies)
	req.Header.Set("referer", fmt.Sprintf("https://x.com/%s/following", screenName))

	q := buildQuery(params)
	variables := map[string]any{
		"userId":                 userID,
		"count":                  20,
		"includePromotedContent": false,
	}
	b, _ := json.Marshal(variables)
	q.Set("variables", string(b))
	req.URL.RawQuery = q.Encode()

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer func() {
		_ = resp.Body.Close()
	}()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d", resp.StatusCode)
	}

	var body map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return nil, err
	}

	data, _ := body["data"].(map[string]any)
	if data == nil {
		return nil, fmt.Errorf("no data in followings response")
	}
	user, _ := data["user"].(map[string]any)
	if user == nil {
		return nil, fmt.Errorf("no user in followings response")
	}
	result, _ := user["result"].(map[string]any)
	if result == nil {
		return nil, fmt.Errorf("no result in followings response")
	}
	timelineWrap, _ := result["timeline"].(map[string]any)
	if timelineWrap == nil {
		return nil, fmt.Errorf("no timeline in followings response")
	}
	timeline, _ := timelineWrap["timeline"].(map[string]any)
	if timeline == nil {
		return nil, fmt.Errorf("no nested timeline in followings response")
	}
	instructionsAny, _ := timeline["instructions"].([]any)
	if instructionsAny == nil {
		return nil, fmt.Errorf("no instructions in followings response")
	}

	var users [][]any

	for _, instrVal := range instructionsAny {
		instr, ok := instrVal.(map[string]any)
		if !ok {
			continue
		}
		if instr["type"] != "TimelineAddEntries" {
			continue
		}
		entriesAny, _ := instr["entries"].([]any)
		for _, entryVal := range entriesAny {
			entry, ok := entryVal.(map[string]any)
			if !ok {
				continue
			}
			content, _ := entry["content"].(map[string]any)
			if content == nil {
				continue
			}
			if content["entryType"] != "TimelineTimelineItem" {
				continue
			}

			itemContent, _ := content["itemContent"].(map[string]any)
			if itemContent == nil {
				continue
			}
			userResults, _ := itemContent["user_results"].(map[string]any)
			if userResults == nil {
				continue
			}
			userResult, _ := userResults["result"].(map[string]any)
			if userResult == nil {
				continue
			}

			core, _ := userResult["core"].(map[string]any)
			if core == nil {
				core = map[string]any{}
			}
			legacy, _ := userResult["legacy"].(map[string]any)
			if legacy == nil {
				legacy = map[string]any{}
			}

			avatarURL := ""
			if avatarAny, ok := userResult["avatar"].(map[string]any); ok {
				if img, ok := avatarAny["image_url"].(string); ok {
					avatarURL = img
				}
			}

			createdAt, _ := core["created_at"].(string)
			username, _ := core["screen_name"].(string)
			name, _ := core["name"].(string)
			bio, _ := legacy["description"].(string)

			var followers int64
			switch v := legacy["followers_count"].(type) {
			case float64:
				followers = int64(v)
			case int64:
				followers = v
			case int:
				followers = int64(v)
			}

			bannerURL, _ := legacy["profile_banner_url"].(string)

			users = append(users, []any{
				avatarURL,
				createdAt,
				username,
				name,
				bio,
				followers,
				bannerURL,
			})
		}
	}

	return users, nil
}

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

func buildQuery(params map[string]any) url.Values {
	q := url.Values{}
	for k, v := range params {
		q.Set(k, fmt.Sprint(v))
	}
	return q
}

// loadRawList читает [][]any из файла (если файла нет — возвращает пустой слайс).
func loadRawList(path string) ([][]any, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	if len(data) == 0 {
		return nil, nil
	}
	var out [][]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func saveRawList(path string, v [][]any) error {
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}

// diffByUsername возвращает элементы current, которых нет в old (по username – индексу 2).
func diffByUsername(oldList, current [][]any) [][]any {
	if len(oldList) == 0 {
		return current
	}
	oldSet := make(map[string]struct{}, len(oldList))
	for _, u := range oldList {
		if len(u) <= 2 {
			continue
		}
		username := fmt.Sprint(u[2])
		if username == "" {
			continue
		}
		oldSet[username] = struct{}{}
	}

	var result [][]any
	for _, u := range current {
		if len(u) <= 2 {
			continue
		}
		username := fmt.Sprint(u[2])
		if username == "" {
			continue
		}
		if _, exists := oldSet[username]; !exists {
			result = append(result, u)
		}
	}
	return result
}

// mergeRawLists делает объединение base и additions по username (индекс 2),
// чтобы один и тот же пользователь никогда не считался "новым" дважды.
func mergeRawLists(base [][]any, additions [][]any) [][]any {
	if len(additions) == 0 {
		return base
	}

	seen := make(map[string]struct{}, len(base))
	for _, u := range base {
		if len(u) <= 2 {
			continue
		}
		username := fmt.Sprint(u[2])
		if username == "" {
			continue
		}
		seen[username] = struct{}{}
	}

	var out [][]any
	out = append(out, base...)

	for _, u := range additions {
		if len(u) <= 2 {
			continue
		}
		username := fmt.Sprint(u[2])
		if username == "" {
			continue
		}
		if _, exists := seen[username]; exists {
			continue
		}
		seen[username] = struct{}{}
		out = append(out, u)
	}

	return out
}

type subscription struct {
	AvatarURL string
	CreatedAt string
	Username  string
	Name      string
	Bio       string
	Followers int64
	BannerURL string
}

func parseUser(raw []any) (subscription, error) {
	getString := func(idx int) string {
		if idx >= len(raw) {
			return ""
		}
		if raw[idx] == nil {
			return ""
		}
		if s, ok := raw[idx].(string); ok {
			return s
		}
		return fmt.Sprint(raw[idx])
	}

	getInt := func(idx int) int64 {
		if idx >= len(raw) || raw[idx] == nil {
			return 0
		}
		switch v := raw[idx].(type) {
		case float64:
			return int64(v)
		case int64:
			return v
		case int:
			return int64(v)
		default:
			return 0
		}
	}

	return subscription{
		AvatarURL: getString(0),
		CreatedAt: getString(1),
		Username:  getString(2),
		Name:      getString(3),
		Bio:       getString(4),
		Followers: getInt(5),
		BannerURL: getString(6),
	}, nil
}

func buildCaption(foundBy string, sub subscription) string {
	var b strings.Builder
	fmt.Fprintf(&b, "<b>New sub by %s</b>\n\n", foundBy)

	if sub.Username != "" {
		fmt.Fprintf(&b, "<b>@%s</b>", sub.Username)
		if sub.Name != "" {
			fmt.Fprintf(&b, " (%s)", sub.Name)
		}
		b.WriteString("\n")
	}

	if sub.Bio != "" {
		fmt.Fprintf(&b, "<code>%s</code>\n\n", sub.Bio)
	}

	if sub.Followers > 0 {
		fmt.Fprintf(&b, "- Followers: %d\n", sub.Followers)
	}

	if sub.CreatedAt != "" {
		formatted := formatTwitterDate(sub.CreatedAt)
		fmt.Fprintf(&b, "- Created: %s\n", formatted)
	}

	if sub.Username != "" {
		profileURL := fmt.Sprintf("https://x.com/%s", sub.Username)
		fmt.Fprintf(&b, "\n🔗 <a href='%s'>Twitter profile</a>", profileURL)
	}

	return b.String()
}

// formatTwitterDate converts Twitter dates like
// "Fri Sep 07 10:56:30 +0000 2007" into "07.09.2007 at 10:56".
func formatTwitterDate(raw string) string {
	const twitterLayout = "Mon Jan 02 15:04:05 -0700 2006"
	const targetLayout = "02.01.2006 at 15:04"

	t, err := time.Parse(twitterLayout, raw)
	if err != nil {
		// если не получилось разобрать — возвращаем как есть
		return raw
	}
	return t.Format(targetLayout)
}
