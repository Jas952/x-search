package config

import (
	"encoding/json"
	"errors"
	"os"
	"strconv"
	"time"
)

// Config описывает основные настройки приложения.
// Значения берём из ENV (и .env, который подхватывается в main.go).
type Config struct {
	// Telegram
	TelegramBotToken string
	TelegramChatID   string

	// Twitter raw JSON (строки из .env)
	TwitterCookiesConfig string
	HeadersIDConfig      string
	ParamsIDConfig       string

	CookiesFollowingConfig string
	HeadersFollowingConfig string
	ParamsFollowingConfig  string

	CookiesBigConfig string
	HeadersBigConfig string
	ParamsBigConfig  string

	CookiesReplyConfig string
	HeadersReplyConfig string
	ParamsReplyConfig  string

	CookiesInfoConfig string
	HeadersInfoConfig string
	ParamsInfoConfig  string

	// Search module
	CookiesSearchConfig string
	HeadersSearchConfig string
	SearchCycleMinutes  int

	HTTPTimeout time.Duration
}

// Load загружает конфигурацию из переменных окружения.
// Критичные параметры (например, BOT_TOKEN и TWITTER_COOKIES_CONFIG) считаются обязательными.
func Load() (*Config, error) {

	timeoutStr := os.Getenv("HTTP_TIMEOUT_SECONDS")
	timeout := 30 * time.Second

	if timeoutStr != "" {
		if n, err := strconv.Atoi(timeoutStr); err == nil && n > 0 {
			timeout = time.Duration(n) * time.Second
		}
	}

	cfg := &Config{
		TelegramBotToken: os.Getenv("TELEGRAM_BOT_TOKEN"),
		TelegramChatID:   os.Getenv("TELEGRAM_CHAT_ID"),

		TwitterCookiesConfig: os.Getenv("TWITTER_COOKIES_CONFIG"),
		HeadersIDConfig:      os.Getenv("HEADERS_ID_CONFIG"),
		ParamsIDConfig:       os.Getenv("PARAMS_ID_CONFIG"),

		CookiesFollowingConfig: os.Getenv("COOKIES_FOLLOWING_CONFIG"),
		HeadersFollowingConfig: os.Getenv("HEADERS_FOLLOWING_CONFIG"),
		ParamsFollowingConfig:  os.Getenv("PARAMS_FOLLOWING_CONFIG"),

		CookiesBigConfig: os.Getenv("COOKIES_BIG_CONFIG"),
		HeadersBigConfig: os.Getenv("HEADERS_BIG_CONFIG"),
		ParamsBigConfig:  os.Getenv("PARAMS_BIG_CONFIG"),

		CookiesReplyConfig: os.Getenv("COOKIES_REPLY_CONFIG"),
		HeadersReplyConfig: os.Getenv("HEADERS_REPLY_CONFIG"),
		ParamsReplyConfig:  os.Getenv("PARAMS_REPLY_CONFIG"),

		CookiesInfoConfig: os.Getenv("COOKIES_INFO_CONFIG"),
		HeadersInfoConfig: os.Getenv("HEADERS_INFO_CONFIG"),
		ParamsInfoConfig:  os.Getenv("PARAMS_INFO_CONFIG"),

		CookiesSearchConfig: os.Getenv("COOKIES_SEARCH_CONFIG"),
		HeadersSearchConfig: os.Getenv("HEADERS_SEARCH_CONFIG"),

		HTTPTimeout: timeout,
	}

	// Search cycle minutes (optional, default 10)
	if v := os.Getenv("SEARCH_CYCLE_MINUTES"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			cfg.SearchCycleMinutes = n
		}
	}
	if cfg.SearchCycleMinutes <= 0 {
		cfg.SearchCycleMinutes = 10
	}

	if cfg.TelegramBotToken == "" {
		return nil, errors.New("TELEGRAM_BOT_TOKEN is required")
	}
	if cfg.TwitterCookiesConfig == "" {
		return nil, errors.New("TWITTER_COOKIES_CONFIG is required")
	}

	return cfg, nil
}

// helpers для парсинга JSON-строк из ENV в map[string]any

func parseDict(raw string) map[string]any {
	if raw == "" {
		return map[string]any{}
	}
	var m map[string]any
	if err := json.Unmarshal([]byte(raw), &m); err != nil {
		return map[string]any{}
	}
	return m
}

func (c *Config) TwitterCookies() map[string]any {
	return parseDict(c.TwitterCookiesConfig)
}

func (c *Config) HeadersID() map[string]any {
	return parseDict(c.HeadersIDConfig)
}

func (c *Config) ParamsID() map[string]any {
	return parseDict(c.ParamsIDConfig)
}

func (c *Config) CookiesFollowing() map[string]any {
	return parseDict(c.CookiesFollowingConfig)
}

func (c *Config) HeadersFollowing() map[string]any {
	return parseDict(c.HeadersFollowingConfig)
}

func (c *Config) ParamsFollowing() map[string]any {
	return parseDict(c.ParamsFollowingConfig)
}

func (c *Config) CookiesBig() map[string]any {
	return parseDict(c.CookiesBigConfig)
}

func (c *Config) HeadersBig() map[string]any {
	return parseDict(c.HeadersBigConfig)
}

func (c *Config) ParamsBig() map[string]any {
	return parseDict(c.ParamsBigConfig)
}

func (c *Config) CookiesReply() map[string]any {
	return parseDict(c.CookiesReplyConfig)
}

func (c *Config) HeadersReply() map[string]any {
	return parseDict(c.HeadersReplyConfig)
}

func (c *Config) ParamsReply() map[string]any {
	return parseDict(c.ParamsReplyConfig)
}

func (c *Config) CookiesInfo() map[string]any {
	return parseDict(c.CookiesInfoConfig)
}

func (c *Config) HeadersInfo() map[string]any {
	return parseDict(c.HeadersInfoConfig)
}

func (c *Config) ParamsInfo() map[string]any {
	return parseDict(c.ParamsInfoConfig)
}

func (c *Config) CookiesSearch() map[string]any {
	return parseDict(c.CookiesSearchConfig)
}

func (c *Config) HeadersSearch() map[string]any {
	return parseDict(c.HeadersSearchConfig)
}
