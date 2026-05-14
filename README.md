# check_x_bot

Twitter/X monitoring bot written in Go. Tracks new followings of target accounts and monitors keyword searches — sends notifications to Telegram.

## Features

- **New subscriptions monitor** — detects when target accounts follow someone new, sends photo + profile info to Telegram
- **Search monitor** — periodically searches Twitter by configurable keyword queries, filters by engagement, deduplicates, sends results to Telegram
- Cookie-based auth 
- Graceful shutdown, structured logging

## Requirements

- Go 1.22+
- A logged-in Twitter account (to extract session cookies)
- A Telegram bot token + chat ID

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd check_x_bot
go mod download
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Twitter cookies and headers (see below)

### 3. Get Twitter cookies & headers

Each bot module requires its own set of cookies + headers captured from a real browser session. Different endpoints may need cookies from different accounts or sessions.

**How to capture:**
1. Log in to [x.com](https://x.com) in your browser
2. Open DevTools → Network tab
3. Navigate to the page corresponding to the endpoint you need (see table below)
4. Find the relevant GraphQL request in the network log
5. Right-click → Copy as cURL
6. Extract cookies and headers into JSON objects and paste into `.env`

**Endpoints and where to capture them:**

| `.env` variable group | Endpoint | Navigate to |
|---|---|---|
| `TWITTER_COOKIES_CONFIG` / `HEADERS_ID_CONFIG` | `UserByScreenName` | Any user profile page |
| `COOKIES_FOLLOWING_CONFIG` / `HEADERS_FOLLOWING_CONFIG` | `Following` | `x.com/<user>/following` |
| `COOKIES_SEARCH_CONFIG` / `HEADERS_SEARCH_CONFIG` | `SearchTimeline` | `x.com/search?q=...` |
| `COOKIES_BIG_CONFIG` / `HEADERS_BIG_CONFIG` | Followers list | `x.com/<user>/followers` |
| `COOKIES_REPLY_CONFIG` / `HEADERS_REPLY_CONFIG` | User tweets/replies | `x.com/<user>/with_replies` |
| `COOKIES_INFO_CONFIG` / `HEADERS_INFO_CONFIG` | User details | Any user profile page |

**Required cookies (for all endpoints):**

| Cookie | Description |
|---|---|
| `auth_token` | Main session auth token |
| `ct0` | CSRF token — **must match** the `x-csrf-token` header |
| `guest_id` | Guest session ID |

**Required headers (for all endpoints):**

| Header | Description |
|---|---|
| `authorization` | Bearer token (starts with `Bearer AAAAAAA...`) — same for all users |
| `x-csrf-token` | Must equal the value of cookie `ct0` |
| `x-twitter-active-user` | Set to `yes` |
| `x-twitter-auth-type` | Set to `OAuth2Session` |

> **Note:** Cookies expire after a few weeks/months. When you start getting 401 errors — re-capture cookies from the browser and update `.env`.

### 4. Configure targets and search queries

Add Twitter usernames to monitor (one per line):
```
modules/new_subs/targets.txt
```

Edit search queries:
```
modules/search/monitor_config.json
```

### 5. Run

```bash
make run
# or
go run ./cmd/app
```

## Project structure

```
cmd/app/            — entry point (main.go)
internal/
  bot/              — main bot loop (tickers for new_subs + search)
  config/           — config loading from .env
  logging/          — unified logger (console + logs/app.log)
  modules/
    new_subs/       — following tracker logic
    search/         — SearchTimeline GraphQL logic
  telegram/         — Telegram Bot API client
modules/
  new_subs/         — runtime data: targets.txt, old_*.json, new_*.json
  search/           — monitor_config.json, seen_tweets.json, reports/
```

## How it works

The bot uses Twitter's **internal GraphQL API** (the same one the web client uses), authenticated via session cookies. No developer account or official API key is required.

See [`skill.md`](./skill.md) for a detailed breakdown of the auth method, endpoints, and request structure.

## Makefile

```bash
make run        # run the bot
make build      # build binary to bin/
make test       # run tests
make lint       # golangci-lint
```

## Disclaimer

This project uses Twitter's internal API via session cookies. Use responsibly and at your own risk. It may violate Twitter's Terms of Service.
# x-search
# x-search
# x-search
