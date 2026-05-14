package last_reply

// (off) Модуль last_reply временно отключён.
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
	baseDirReply      = "modules/(off) last_reply"
	targetsFileReply  = "targets.txt"
	newRepliesDir     = "new_replies"
	sleepBetweenReply = time.Second
)

// Process обрабатывает новые replies и отправляет ссылки в Telegram.
// Аналог Python-функции process_new_replies, но модуль пока (off) и
// не вызывается из основного цикла.
func Process(ctx context.Context, tg *telegram.Client) error {
	logging.LogInfo("last_reply: starting processing (off module)")

	targets, err := loadTargets()
	if err != nil {
		return fmt.Errorf("last_reply: load targets: %w", err)
	}
	if len(targets) == 0 {
		logging.LogWarn("last_reply: no targets in targets.txt")
		return nil
	}

	var total int

	for _, username := range targets {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		filePath := filepath.Join(baseDirReply, newRepliesDir, fmt.Sprintf("new_%s_replies.json", username))
		f, err := os.Open(filePath)
		if err != nil {
			if os.IsNotExist(err) {
				logging.LogDebug("last_reply: no new_replies file for user",
					logging.String("user", username),
				)
				continue
			}
			return fmt.Errorf("last_reply: open file for %s: %w", username, err)
		}

		var replies []map[string]any
		if err := json.NewDecoder(f).Decode(&replies); err != nil {
			_ = f.Close()
			logging.LogError("last_reply: failed to decode replies",
				logging.String("file", filePath),
				logging.Err(err),
			)
			continue
		}
		_ = f.Close()

		if len(replies) == 0 {
			continue
		}

		logging.LogInfo("last_reply: processing replies for user",
			logging.String("user", username),
		)

		for _, reply := range replies {
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
			}

			msg := formatReplyMessage(username, reply)
			if msg == "" {
				continue
			}

			if err := tg.SendMessage(ctx, msg); err != nil {
				logging.LogError("last_reply: failed to send Telegram message",
					logging.String("user", username),
					logging.Err(err),
				)
				continue
			}

			total++
			time.Sleep(sleepBetweenReply)
		}
	}

	if total == 0 {
		logging.LogInfo("last_reply: no replies sent in this cycle")
	} else {
		logging.LogSuccess(fmt.Sprintf("last_reply: processed %d replies", total))
	}

	return nil
}

func loadTargets() ([]string, error) {
	path := filepath.Join(baseDirReply, targetsFileReply)
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

func formatReplyMessage(username string, reply map[string]any) string {
	v, ok := reply["reply_id"]
	if !ok || v == nil {
		return ""
	}
	replyID, ok := v.(string)
	if !ok || replyID == "" {
		return ""
	}

	url := fmt.Sprintf("https://fxtwitter.com/%s/status/%s", username, replyID)
	return fmt.Sprintf(`<a href="%s">New replies by @%s</a>`, url, username)
}
