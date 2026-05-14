package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/joho/godotenv"

	"check_x_bot/internal/bot"
	"check_x_bot/internal/config"
	"check_x_bot/internal/logging"
)

func main() {
	// Инициализация .env
	_ = godotenv.Load()

	// Инициализация логера
	if err := logging.InitLogger(); err != nil {
		// если логер не поднялся — падаем максимально рано
		panic(err)
	}
	defer logging.Sync()

	logging.LogSuccess("Application starting")

	// Загрузка конфигурации
	cfg, err := config.Load()
	if err != nil {
		logging.LogError("Failed to load config", logging.Err(err))
		os.Exit(1)
	}

	// Контекст с graceful shutdown
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	// Запуск основного бота
	if err := bot.Run(ctx, cfg); err != nil {
		logging.LogError("Bot terminated with error", logging.Err(err))
	} else {
		logging.LogSuccess("Bot stopped gracefully")
	}

	// Небольшой таймаут, чтобы дать логеру сбросить буферы
	time.Sleep(200 * time.Millisecond)
}


