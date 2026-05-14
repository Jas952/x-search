# Skill: Обращение к Twitter (X) через cookies + GraphQL

## Общий принцип

Проект **не использует** официальный Twitter API v2 с OAuth-токенами.  
Вместо этого применяется **реверс-инженерия внутреннего GraphQL API** сайта `x.com` — тот же API, что использует веб-клиент Twitter в браузере.

Авторизация происходит через **cookies сессии** реального залогиненного пользователя + набор **HTTP-заголовков**, которые браузер отправляет при обычном использовании сайта.

---

## Как это работает (пошагово)

### 1. Получение cookies и заголовков

1. Залогиньтесь в Twitter (x.com) в браузере.
2. Откройте DevTools → Network.
3. Перейдите на страницу, чей API хотите перехватить (например, `x.com/<user>/following`).
4. Найдите GraphQL-запрос (например, `UserByScreenName`, `Following`, `SearchTimeline`).
5. Скопируйте из запроса:
   - **Cookies** — все куки сессии (как JSON-объект `{"key": "value", ...}`).
   - **Headers** — заголовки запроса (особенно `authorization`, `x-csrf-token`, `x-twitter-active-user`, `x-twitter-auth-type`, `x-client-transaction-id` и т.д.).
   - **Params** — query-параметры (`variables`, `features`, `fieldToggles`).

### 2. Конфигурация через `.env`

Все cookies, headers и params сохраняются в `.env` как **JSON-строки**:

```env
# Cookies для запросов UserByScreenName (получение user ID)
TWITTER_COOKIES_CONFIG='{"auth_token":"xxx","ct0":"yyy","guest_id":"zzz",...}'

# Заголовки для UserByScreenName
HEADERS_ID_CONFIG='{"authorization":"Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejR...","x-csrf-token":"yyy",...}'

# Query-параметры (features, fieldToggles)
PARAMS_ID_CONFIG='{"features":"{...}","fieldToggles":"{...}"}'

# Аналогично для других эндпоинтов:
COOKIES_FOLLOWING_CONFIG='...'
HEADERS_FOLLOWING_CONFIG='...'
PARAMS_FOLLOWING_CONFIG='...'

COOKIES_SEARCH_CONFIG='...'
HEADERS_SEARCH_CONFIG='...'
```

### 3. Загрузка конфигурации в Go

Файл `internal/config/config.go`:

- Все JSON-строки читаются из `os.Getenv(...)` при старте.
- Для каждого набора есть метод-accessor, который парсит JSON в `map[string]any`:

```go
func (c *Config) TwitterCookies() map[string]any {
    return parseDict(c.TwitterCookiesConfig) // json.Unmarshal
}
```

### 4. Применение cookies и headers к HTTP-запросу

Функция `applyHeadersAndCookies(req, headers, cookies)`:

```go
func applyHeadersAndCookies(req *http.Request, headers, cookies map[string]any) {
    // Устанавливаем все заголовки
    for k, v := range headers {
        req.Header.Set(k, fmt.Sprint(v))
    }
    // Собираем cookies в строку "key1=val1; key2=val2; ..."
    var parts []string
    for k, v := range cookies {
        parts = append(parts, fmt.Sprintf("%s=%v", k, v))
    }
    req.Header.Set("Cookie", strings.Join(parts, "; "))
}
```

**Важно**: cookies передаются НЕ через `http.CookieJar`, а напрямую через заголовок `Cookie`.

---

## Используемые GraphQL-эндпоинты

### UserByScreenName — получение user ID по нику

```
GET https://x.com/i/api/graphql/{queryID}/UserByScreenName
```

- **Вход**: `variables: {"screen_name": "elonmusk"}`
- **Выход**: `data.user.result.rest_id` — числовой ID пользователя
- **Заголовок `referer`**: `https://x.com/{username}/following`

### Following — список подписок пользователя

```
GET https://x.com/i/api/graphql/{queryID}/Following
```

- **Вход**: `variables: {"userId": "...", "count": 20, "includePromotedContent": false}`
- **Выход**: массив пользователей из `data.user.result.timeline.timeline.instructions[].entries[].content.itemContent.user_results.result`
- Из каждого user извлекаются: `avatar`, `core.screen_name`, `core.name`, `core.created_at`, `legacy.description`, `legacy.followers_count`, `legacy.profile_banner_url`

### SearchTimeline — поиск твитов

```
GET/POST https://x.com/i/api/graphql/{queryID}/SearchTimeline
```

- **Вход**: `variables: {"rawQuery": "...", "count": 20, "querySource": "typed_query", "product": "Latest"|"Top"}`
- **Features**: большой набор GraphQL feature flags (см. `searchFeatures` в коде)
- **Fallback-стратегия**: пробуем 3 метода отправки запроса:
  1. `POST` с JSON body (`variables` + `features` в теле)
  2. `GET` с query-параметрами (`variables` + `features` в URL)
  3. `POST` с query-параметрами (гибрид)
- **Пагинация**: через `cursor` из `cursor-bottom` entry
- **Query ID**: захардкожены несколько кандидатов, перебираются при ошибках

---

## Обработка ошибок и rate limiting

- **429 Too Many Requests**: читаем `x-rate-limit-reset` из заголовка ответа, вычисляем время ожидания (5–120 секунд), спим и повторяем запрос.
- **400/404**: считаем, что метод отправки неверный, пробуем следующий.
- **Запоминание рабочего метода**: `lastWorkingMethod` сохраняет последний успешный способ отправки, чтобы не перебирать каждый раз.

---

## Формат данных подписок

Подписки хранятся как `[][]any` (массив массивов), каждый элемент:

```
[0] avatarURL    string
[1] createdAt    string  (формат Twitter: "Fri Sep 07 10:56:30 +0000 2007")
[2] username     string  (screen_name) — ключ для дедупликации
[3] name         string  (display name)
[4] bio          string  (описание профиля)
[5] followers    int64   (количество подписчиков)
[6] bannerURL    string  (баннер профиля)
```

---

## Критические заголовки для авторизации

Без этих заголовков запросы вернут 401/403:

| Заголовок | Описание |
|-----------|----------|
| `authorization` | Bearer-токен Twitter (начинается с `Bearer AAAAAAAAAAAAA...`) — **публичный**, одинаковый для всех пользователей |
| `x-csrf-token` | CSRF-токен, совпадает со значением cookie `ct0` |
| `cookie` | Полная строка cookies сессии (`auth_token`, `ct0`, `guest_id`, и др.) |
| `referer` | URL страницы, с которой "якобы" отправлен запрос |

---

## Время жизни и обновление cookies

- Cookies сессии Twitter **живут ограниченное время** (обычно несколько недель/месяцев).
- При протухании cookies API начнёт возвращать 401.
- **Обновление**: вручную — заново залогиниться, перехватить cookies через DevTools, обновить `.env`.
- `auth_token` и `ct0` — самые важные cookies для авторизации.

---

## Схема работы бота

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐
│   .env      │────>│  config.Load()   │────>│  HTTP Client   │
│ (cookies,   │     │  parseDict()     │     │  + headers     │
│  headers,   │     │                  │     │  + cookies     │
│  params)    │     └──────────────────┘     └───────┬────────┘
└─────────────┘                                     │
                                                    ▼
                                          ┌─────────────────┐
                                          │  x.com GraphQL  │
                                          │  API endpoints  │
                                          └────────┬────────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │  Parse JSON     │
                                          │  response       │
                                          └────────┬────────┘
                                                   │
                              ┌────────────────────┼────────────────────┐
                              ▼                    ▼                    ▼
                    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
                    │  new_subs    │     │   search     │     │  Telegram    │
                    │  diff/save   │     │  filter/     │     │  notify      │
                    │  old_/new_   │     │  dedupe      │     │              │
                    └──────────────┘     └──────────────┘     └──────────────┘
```

---

## Резюме

- **Метод авторизации**: cookies сессии + HTTP-заголовки из браузера
- **API**: внутренний GraphQL API x.com (НЕ официальный Twitter API v2)
- **Преимущество**: не нужен developer-аккаунт, нет лимитов official API
- **Недостаток**: cookies протухают, query ID меняются, формат ответов может измениться без предупреждения
- **Хранение секретов**: `.env` файл (в `.gitignore`)
