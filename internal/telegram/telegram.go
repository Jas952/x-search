package telegram

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"check_x_bot/internal/logging"
)

type Client struct {
	token    string
	chatID   string
	baseURL  string
	httpClient *http.Client
}

func NewClient(token, chatID string) *Client {
	return &Client{
		token:   token,
		chatID:  chatID,
		baseURL: fmt.Sprintf("https://api.telegram.org/bot%s", token),
		httpClient: &http.Client{
			Timeout: 15 * time.Second,
		},
	}
}

type apiResponse struct {
	OK          bool            `json:"ok"`
	Description string          `json:"description,omitempty"`
	Result      json.RawMessage `json:"result,omitempty"`
}

func (c *Client) SendMessage(ctx context.Context, text string) error {
	payload := map[string]any{
		"chat_id":                  c.chatID,
		"text":                     text,
		"parse_mode":               "HTML",
		"disable_web_page_preview": false,
	}
	return c.postJSON(ctx, "/sendMessage", payload)
}

func (c *Client) SendPhoto(ctx context.Context, photoURL, caption string) error {
	payload := map[string]any{
		"chat_id":    c.chatID,
		"photo":      photoURL,
		"caption":    caption,
		"parse_mode": "HTML",
	}
	return c.postJSON(ctx, "/sendPhoto", payload)
}

func (c *Client) postJSON(ctx context.Context, path string, payload map[string]any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal payload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("send request: %w", err)
	}
	defer func() {
		_ = resp.Body.Close()
	}()

	var apiResp apiResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return fmt.Errorf("decode response: %w", err)
	}

	if !apiResp.OK {
		logging.LogError("Telegram API error",
			logging.String("description", apiResp.Description),
			logging.Int("status", resp.StatusCode),
		)
		return fmt.Errorf("telegram api error: %s", apiResp.Description)
	}

	return nil
}


