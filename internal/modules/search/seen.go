package search

import (
	"encoding/json"
	"os"
	"path/filepath"
)

const defaultMaxSeen = 50_000

// SeenTracker persists a set of tweet IDs to avoid duplicate notifications.
type SeenTracker struct {
	path    string
	maxSize int
	ids     map[string]struct{}
	order   []string // insertion order for trimming
}

type seenFile struct {
	Seen  []string `json:"seen"`
	Count int      `json:"count"`
}

// NewSeenTracker creates a tracker backed by the given JSON file.
func NewSeenTracker(path string, maxSize int) *SeenTracker {
	if maxSize <= 0 {
		maxSize = defaultMaxSeen
	}
	return &SeenTracker{
		path:    path,
		maxSize: maxSize,
		ids:     make(map[string]struct{}),
	}
}

// Load reads the seen set from disk.
func (s *SeenTracker) Load() error {
	data, err := os.ReadFile(s.path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	var f seenFile
	if err := json.Unmarshal(data, &f); err != nil {
		return err
	}
	s.ids = make(map[string]struct{}, len(f.Seen))
	s.order = make([]string, 0, len(f.Seen))
	for _, id := range f.Seen {
		if _, ok := s.ids[id]; !ok {
			s.ids[id] = struct{}{}
			s.order = append(s.order, id)
		}
	}
	return nil
}

// Save writes the seen set to disk, trimming to maxSize.
func (s *SeenTracker) Save() error {
	// trim oldest if over limit
	if len(s.order) > s.maxSize {
		excess := len(s.order) - s.maxSize
		for _, id := range s.order[:excess] {
			delete(s.ids, id)
		}
		s.order = s.order[excess:]
	}

	dir := filepath.Dir(s.path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}

	f := seenFile{Seen: s.order, Count: len(s.order)}
	data, err := json.Marshal(f)
	if err != nil {
		return err
	}
	return os.WriteFile(s.path, data, 0o644)
}

// IsSeen returns true if the tweet ID was already processed.
func (s *SeenTracker) IsSeen(id string) bool {
	_, ok := s.ids[id]
	return ok
}

// MarkSeen adds a tweet ID to the seen set.
func (s *SeenTracker) MarkSeen(id string) {
	if _, ok := s.ids[id]; ok {
		return
	}
	s.ids[id] = struct{}{}
	s.order = append(s.order, id)
}

// FilterNew returns tweets not yet seen and marks them as seen.
func (s *SeenTracker) FilterNew(tweets []TweetData) []TweetData {
	var result []TweetData
	for _, t := range tweets {
		if !s.IsSeen(t.ID) {
			s.MarkSeen(t.ID)
			result = append(result, t)
		}
	}
	return result
}

// Count returns the number of seen tweet IDs.
func (s *SeenTracker) Count() int {
	return len(s.ids)
}
