package search

import (
	"crypto/md5"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

const (
	cacheDir    = "modules/search/cache"
	defaultCTTL = 15 * time.Minute
)

type cacheEntry struct {
	Query     string      `json:"query"`
	Params    string      `json:"params"`
	Timestamp int64       `json:"timestamp"`
	Tweets    []TweetData `json:"tweets"`
}

func cacheKey(query, params string) string {
	h := md5.Sum([]byte(query + "|" + params))
	return fmt.Sprintf("%x", h)[:12]
}

// CacheGet returns cached tweets if available and not expired.
func CacheGet(query, params string, ttl time.Duration) ([]TweetData, bool) {
	if ttl == 0 {
		ttl = defaultCTTL
	}
	key := cacheKey(query, params)
	path := filepath.Join(cacheDir, key+".json")

	data, err := os.ReadFile(path)
	if err != nil {
		return nil, false
	}

	var e cacheEntry
	if err := json.Unmarshal(data, &e); err != nil {
		return nil, false
	}

	if time.Since(time.UnixMilli(e.Timestamp)) > ttl {
		return nil, false
	}
	return e.Tweets, true
}

// CacheSet writes tweets to the file cache.
func CacheSet(query, params string, tweets []TweetData) {
	_ = os.MkdirAll(cacheDir, 0o755)

	key := cacheKey(query, params)
	e := cacheEntry{
		Query:     query,
		Params:    params,
		Timestamp: time.Now().UnixMilli(),
		Tweets:    tweets,
	}

	data, err := json.Marshal(e)
	if err != nil {
		return
	}
	_ = os.WriteFile(filepath.Join(cacheDir, key+".json"), data, 0o644)
}

// CachePrune removes expired entries from the cache directory.
func CachePrune(ttl time.Duration) int {
	if ttl == 0 {
		ttl = defaultCTTL
	}
	entries, err := os.ReadDir(cacheDir)
	if err != nil {
		return 0
	}

	removed := 0
	for _, de := range entries {
		if de.IsDir() {
			continue
		}
		path := filepath.Join(cacheDir, de.Name())
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		var e cacheEntry
		if err := json.Unmarshal(data, &e); err != nil {
			_ = os.Remove(path)
			removed++
			continue
		}
		if time.Since(time.UnixMilli(e.Timestamp)) > ttl {
			_ = os.Remove(path)
			removed++
		}
	}
	return removed
}
