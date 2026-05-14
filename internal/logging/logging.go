package logging

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

var (
	logger     *zap.Logger
	loggerOnce sync.Once
)

const (
	// maxLogSizeBytes is a hard limit for logs/app.log.
	// If the file grows beyond this size, it will be truncated on the next startup.
	maxLogSizeBytes = 10 * 1024 * 1024 // 10 MB
)

// InitLogger инициализирует глобальный логер.
// - Создаёт директорию logs
// - Открывает файл logs/app.log
// - Настраивает вывод в файл (все уровни) и красивый вывод в консоль
func InitLogger() error {
	var initErr error
	loggerOnce.Do(func() {
		if err := os.MkdirAll("logs", 0o755); err != nil {
			initErr = fmt.Errorf("create logs dir: %w", err)
			return
		}

		logPath := filepath.Join("logs", "app.log")

		// truncate log file if it grows too large
		if info, err := os.Stat(logPath); err == nil && info.Size() > maxLogSizeBytes {
			// best-effort cleanup; ignore error
			_ = os.Truncate(logPath, 0)
		}

		file, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
		if err != nil {
			initErr = fmt.Errorf("open log file: %w", err)
			return
		}

		// Кодировщик для файла
		fileEncoderCfg := zapcore.EncoderConfig{
			TimeKey:        "ts",
			LevelKey:       "level",
			NameKey:        "logger",
			CallerKey:      "caller",
			MessageKey:     "msg",
			StacktraceKey:  "stack",
			LineEnding:     zapcore.DefaultLineEnding,
			EncodeLevel:    zapcore.CapitalLevelEncoder,
			EncodeTime:     encodeFileTime,
			EncodeDuration: zapcore.SecondsDurationEncoder,
		}

		fileCore := zapcore.NewCore(
			zapcore.NewConsoleEncoder(fileEncoderCfg),
			zapcore.AddSync(file),
			zapcore.DebugLevel,
		)

		// Консольный вывод — только ключевые события
		consoleCore := zapcore.NewCore(
			newConsoleEncoder(),
			zapcore.AddSync(os.Stdout),
			zapcore.InfoLevel,
		)

		core := zapcore.NewTee(fileCore, consoleCore)
		logger = zap.New(core, zap.AddCaller(), zap.AddCallerSkip(1))
	})

	return initErr
}

func encodeFileTime(t time.Time, enc zapcore.PrimitiveArrayEncoder) {
	enc.AppendString(t.Format("2006-01-02 15:04:05"))
}

// цветовые коды ANSI
const (
	colorReset  = "\033[0m"
	colorGreen  = "\033[32m"
	colorRed    = "\033[31m"
	colorYellow = "\033[33m"
	colorBlue   = "\033[34m"
)

func newConsoleEncoder() zapcore.Encoder {
	return zapcore.NewConsoleEncoder(zapcore.EncoderConfig{
		TimeKey:       "T",
		LevelKey:      "L",
		MessageKey:    "M",
		EncodeTime:    encodeConsoleTime,
		EncodeLevel:   zapcore.CapitalLevelEncoder,
		LineEnding:    zapcore.DefaultLineEnding,
		EncodeCaller:  zapcore.ShortCallerEncoder,
		EncodeName:    zapcore.FullNameEncoder,
		StacktraceKey: "",
	})
}

func encodeConsoleTime(t time.Time, enc zapcore.PrimitiveArrayEncoder) {
	enc.AppendString(t.Format("15:04:05"))
}

// Общий helper для доступа к logger.
func l() *zap.Logger {
	if logger == nil {
		_ = InitLogger()
	}
	return logger
}

// Поля-обёртки, чтобы не тянуть zap в каждый пакет
func String(key, val string) zap.Field  { return zap.String(key, val) }
func Int(key string, val int) zap.Field { return zap.Int(key, val) }
func Err(err error) zap.Field           { return zap.Error(err) }

// LogInfo пишет обычное информационное сообщение.
func LogInfo(msg string, fields ...zap.Field) {
	l().Info(msg, fields...)
}

// LogSuccess выводит красивый SUCCESS в консоль и пишет INFO в файл.
func LogSuccess(msg string, fields ...zap.Field) {
	console := fmt.Sprintf("%s%s     ✓ SUCCESS %s%s", colorGreen, time.Now().Format("15:04:05"), msg, colorReset)
	fmt.Println(console)
	l().Info(msg, fields...)
}

// LogError выводит ERROR в консоль и пишет ERROR в файл.
func LogError(msg string, fields ...zap.Field) {
	console := fmt.Sprintf("%s%s     ✗ ERROR %s%s", colorRed, time.Now().Format("15:04:05"), msg, colorReset)
	fmt.Println(console)
	l().Error(msg, fields...)
}

// LogWarn пишет WARN (по желанию — можно расширить консольный вывод).
func LogWarn(msg string, fields ...zap.Field) {
	console := fmt.Sprintf("%s%s     ! WARN %s%s", colorYellow, time.Now().Format("15:04:05"), msg, colorReset)
	fmt.Println(console)
	l().Warn(msg, fields...)
}

// LogDebug пишет DEBUG только в файл.
func LogDebug(msg string, fields ...zap.Field) {
	l().Debug(msg, fields...)
}

// Sync финализирует логер.
func Sync() {
	if logger != nil {
		_ = logger.Sync()
	}
}


