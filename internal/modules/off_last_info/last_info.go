package last_info

// (off) Модуль last_info временно отключён.
// Логика порта из старого Python-бота реализована ниже, но модуль
// не подключён к основному циклу. Активировать можно будет позже.

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"check_x_bot/internal/logging"
	"check_x_bot/internal/telegram"
)

const (
	baseDirInfo      = "modules/(off) last_info"
	targetsFileInfo  = "targets.txt"
	newInfoDir       = "new_info"
	sleepBetweenInfo = time.Second
)

// Process обрабатывает новые посты (info) и отправляет ссылки в Telegram.
// Аналог Python-функции process_new_posts, но модуль пока (off) и
// не вызывается из основного цикла.
func Process(ctx context.Context, tg *telegram.Client) error {
	logging.LogInfo("last_info: starting processing (off module)")

	targets, err := loadTargets()
	if err != nil {
		return fmt.Errorf("last_info: load targets: %w", err)
	}
	if len(targets) == 0 {
		logging.LogWarn("last_info: no targets in targets.txt")
		return nil
	}

	var total int

	for _, username := range targets {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		filePath := filepath.Join(baseDirInfo, newInfoDir, fmt.Sprintf("new_%s_info.json", username))
		f, err := os.Open(filePath)
		if err != nil {
			if os.IsNotExist(err) {
				logging.LogDebug("last_info: no new_info file for user",
					logging.String("user", username),
				)
				continue
			}
			return fmt.Errorf("last_info: open file for %s: %w", username, err)
		}

		var posts []map[string]any
		if err := json.NewDecoder(f).Decode(&posts); err != nil {
			_ = f.Close()
			logging.LogError("last_info: failed to decode posts",
				logging.String("file", filePath),
				logging.Err(err),
			)
			continue
		}
		_ = f.Close()

		if len(posts) == 0 {
			continue
		}

		logging.LogInfo("last_info: processing posts for user",
			logging.String("user", username),
		)

		for _, post := range posts {
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
			}

			msg := formatPostMessage(username, post)
			if msg == "" {
				continue
			}

			if err := tg.SendMessage(ctx, msg); err != nil {
				logging.LogError("last_info: failed to send Telegram message",
					logging.String("user", username),
					logging.Err(err),
				)
				continue
			}

			total++
			time.Sleep(sleepBetweenInfo)
		}
	}

	if total == 0 {
		logging.LogInfo("last_info: no posts sent in this cycle")
	} else {
		logging.LogSuccess(fmt.Sprintf("last_info: processed %d posts", total))
	}

	return nil
}

func loadTargets() ([]string, error) {
	path := filepath.Join(baseDirInfo, targetsFileInfo)
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	lines := strings.Split(string(data), "\n")
	var targets []string
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		targets = append(targets, strings.TrimPrefix(line, "@"))
	}
	return targets, nil
}

func formatPostMessage(username string, post map[string]any) string {
	getString := func(key string) string {
		v, ok := post[key]
		if !ok || v == nil {
			return ""
		}
		if s, ok := v.(string); ok {
			return s
		}
		return fmt.Sprint(v)
	}

	postID := getString("id")
	fullText := getString("full_text")

	if postID == "" || fullText == "" {
		return ""
	}

	isRetweet := strings.Contains(fullText, "RT @")
	url := fmt.Sprintf("https://fxtwitter.com/%s/status/%s", username, postID)

	if isRetweet {
		return fmt.Sprintf(`<a href="%s">New repost by @%s</a>`, url, username)
	}
	return fmt.Sprintf(`<a href="%s">New post by @%s</a>`, url, username)
}
