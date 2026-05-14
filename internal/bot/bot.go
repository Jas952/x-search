package bot

import (
	"context"
	"time"

	"check_x_bot/internal/config"
	"check_x_bot/internal/logging"
	"check_x_bot/internal/modules/new_subs"
	"check_x_bot/internal/modules/search"
	"check_x_bot/internal/telegram"
)

// interval between full subscription checks
// currently 5 minutes to reduce Twitter rate limit issues
const subsScanInterval = 5 * time.Minute

// Run — точка входа бизнес-логики бота.
// Здесь будет основной цикл: работа с Twitter (подписки, посты, replies)
// и отправка уведомлений (Discord/Telegram).
func Run(ctx context.Context, cfg *config.Config) error {
	logging.LogInfo("Starting bot loop (new_subs + search)")

	tg := telegram.NewClient(cfg.TelegramBotToken, cfg.TelegramChatID)

	// синхронизируем состояние файлов old_/new_ с текущими таргетами
	if err := new_subs.SyncFilesWithTargets(); err != nil {
		logging.LogError("Failed to sync new_subs files with targets", logging.Err(err))
	}

	// основной цикл — new_subs + search monitor на разных интервалах
	subsTicker := time.NewTicker(subsScanInterval)
	defer subsTicker.Stop()

	searchInterval := time.Duration(cfg.SearchCycleMinutes) * time.Minute
	searchTicker := time.NewTicker(searchInterval)
	defer searchTicker.Stop()

	logging.LogInfo("Search monitor enabled",
		logging.Int("interval_min", cfg.SearchCycleMinutes))

	for {
		select {
		case <-ctx.Done():
			logging.LogInfo("Shutdown signal received, stopping bot loop")
			return nil

		case <-subsTicker.C:
			// 1) сканируем Twitter и обновляем old_*/new_*
			if err := new_subs.ScanAndUpdateSubscriptions(ctx, cfg); err != nil {
				logging.LogError("new_subs scan failed", logging.Err(err))
			}

			// 2) отправляем новые подписки из new_*.json в Telegram
			if err := new_subs.ProcessNewSubscriptions(ctx, cfg, tg); err != nil {
				logging.LogError("new_subs send failed", logging.Err(err))
			} else {
				logging.LogSuccess("new_subs cycle completed")
			}

		case <-searchTicker.C:
			if err := search.RunMonitorCycle(ctx, cfg, tg); err != nil {
				logging.LogError("search monitor cycle failed", logging.Err(err))
			} else {
				logging.LogSuccess("search monitor cycle completed")
			}
		}
	}
}
