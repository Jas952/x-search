package big_follow

// (off) Модуль big_follow временно отключён.
// Ниже портирована логика обработки новых больших подписчиков из Python-бота,
// но модуль не подключён к основному циклу. В будущем можно будет:
//   - включить его в цикл,
//   - добавить получение данных из Twitter (scan_big_followers).

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
	baseDirBig      = "modules/(off) big_follow"
	newBigDir       = "new_big"
	bigTargetsFile  = "bigfollow.txt"
	sleepBetweenBig = time.Second
)

// Process отправляет новых "больших" подписчиков из new_big в Telegram.
// Это аналог send_new_big_followers_to_discord, но переписанный на Telegram.
func Process(ctx context.Context, tg *telegram.Client) error {
	logging.LogInfo("big_follow: starting processing (off module)")

	newDir := filepath.Join(baseDirBig, newBigDir)
	entries, err := os.ReadDir(newDir)
	if err != nil {
		if os.IsNotExist(err) {
			logging.LogDebug("big_follow: new_big dir does not exist, nothing to send")
			return nil
		}
		return fmt.Errorf("big_follow: read new_big dir: %w", err)
	}

	filesProcessed := 0

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !strings.HasSuffix(name, ".json") || strings.HasPrefix(name, ".") {
			continue
		}

		filePath := filepath.Join(newDir, name)
		f, err := os.Open(filePath)
		if err != nil {
			logging.LogError("big_follow: failed to open file",
				logging.String("file", filePath),
				logging.Err(err),
			)
			continue
		}

		var users [][]any
		if err := json.NewDecoder(f).Decode(&users); err != nil {
			_ = f.Close()
			logging.LogError("big_follow: failed to decode json",
				logging.String("file", filePath),
				logging.Err(err),
			)
			continue
		}
		_ = f.Close()

		if len(users) == 0 {
			logging.LogWarn("big_follow: file is empty, skipping",
				logging.String("file", name),
			)
			continue
		}

		usernameBig := strings.TrimPrefix(name, "new_")
		usernameBig = strings.TrimSuffix(usernameBig, "_followers.json")

		logging.LogInfo("big_follow: sending big followers",
			logging.String("target", usernameBig),
			logging.Int("count", len(users)),
		)

		for i, user := range users {
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
			}

			big, err := parseBigFollower(user)
			if err != nil {
				logging.LogWarn("big_follow: failed to parse big follower",
					logging.Int("index", i),
					logging.Err(err),
				)
				continue
			}

			if big.FollowersCount <= 0 {
				// В оригинале был порог 1500+ followers; здесь просто пропускаем,
				// если счётчик невалиден. Порог можно добавить позже.
				logging.LogDebug("big_follow: follower without valid followers_count, skip",
					logging.String("username", big.Username),
				)
				continue
			}

			caption := buildBigCaption(usernameBig, big)

			var photoURL string
			if big.BannerURL != "" {
				photoURL = big.BannerURL
			} else if big.AvatarURL != "" {
				photoURL = big.AvatarURL
			}

			var sendErr error
			if photoURL != "" {
				sendErr = tg.SendPhoto(ctx, photoURL, caption)
			} else {
				sendErr = tg.SendMessage(ctx, caption)
			}

			if sendErr != nil {
				logging.LogError("big_follow: failed to send Telegram message",
					logging.String("username", big.Username),
					logging.Err(sendErr),
				)
				continue
			}

			logging.LogSuccess("big_follow: big follower sent to Telegram",
				logging.String("username", big.Username),
				logging.String("target", usernameBig),
			)

			time.Sleep(sleepBetweenBig)
		}

		filesProcessed++
	}

	logging.LogInfo("big_follow: processing finished",
		logging.Int("files_processed", filesProcessed),
	)

	return nil
}

type bigFollower struct {
	AvatarURL      string
	CreatedAt      string
	Username       string
	Name           string
	Description    string
	FollowersCount int64
	BannerURL      string
}

func parseBigFollower(raw []any) (bigFollower, error) {
	getString := func(idx int) string {
		if idx >= len(raw) || raw[idx] == nil {
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

	return bigFollower{
		AvatarURL:      getString(0),
		CreatedAt:      getString(1),
		Username:       getString(2),
		Name:           getString(3),
		Description:    getString(4),
		FollowersCount: getInt(5),
		BannerURL:      getString(6),
	}, nil
}

func buildBigCaption(target string, bf bigFollower) string {
	var b strings.Builder

	// Заголовок: кто на кого подписался
	fmt.Fprintf(&b, "<b>%s subscribed to %s</b>\n\n", escapeHTML("@"+bf.Username), escapeHTML("@"+target))

	if bf.Name != "" {
		fmt.Fprintf(&b, "<b>%s</b>\n", escapeHTML(bf.Name))
	}

	if bf.Description != "" {
		fmt.Fprintf(&b, "<code>%s</code>\n\n", escapeHTML(bf.Description))
	}

	if bf.FollowersCount > 0 {
		fmt.Fprintf(&b, "- Followers: %d\n", bf.FollowersCount)
	}

	if bf.CreatedAt != "" {
		fmt.Fprintf(&b, "- Created at: %s\n", escapeHTML(bf.CreatedAt))
	}

	if bf.Username != "" {
		profileURL := fmt.Sprintf("https://x.com/%s", bf.Username)
		fmt.Fprintf(&b, "\n🔗 <a href='%s'>Twitter profile</a>", profileURL)
	}

	return b.String()
}

// Простая экранизация для HTML в Telegram (минимальная защита от спецсимволов).
func escapeHTML(s string) string {
	replacer := strings.NewReplacer(
		"&", "&amp;",
		"<", "&lt;",
		">", "&gt;",
	)
	return replacer.Replace(s)
}
