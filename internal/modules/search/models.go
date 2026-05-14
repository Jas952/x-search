package search

// TweetData represents a parsed tweet from the GraphQL SearchTimeline response.
type TweetData struct {
	ID             string       `json:"id"`
	Text           string       `json:"text"`
	AuthorID       string       `json:"author_id"`
	Username       string       `json:"username"`
	Name           string       `json:"name"`
	CreatedAt      string       `json:"created_at"`
	ConversationID string       `json:"conversation_id"`
	Metrics        TweetMetrics `json:"metrics"`
	URLs           []string     `json:"urls"`
	Mentions       []string     `json:"mentions"`
	Hashtags       []string     `json:"hashtags"`
	TweetURL       string       `json:"tweet_url"`
}

// TweetMetrics holds engagement counters for a tweet.
type TweetMetrics struct {
	Likes       int `json:"likes"`
	Retweets    int `json:"retweets"`
	Replies     int `json:"replies"`
	Quotes      int `json:"quotes"`
	Impressions int `json:"impressions"`
	Bookmarks   int `json:"bookmarks"`
}

// QueryConfig describes a single search query from monitor_config.json.
type QueryConfig struct {
	Name     string `json:"name"`
	Query    string `json:"query"`
	Sort     string `json:"sort"`     // "latest" or "top"
	Priority string `json:"priority"` // "high", "medium", "low"
	MinLikes int    `json:"min_likes"`
}

// MonitorConfig is the top-level config loaded from modules/search/monitor_config.json.
type MonitorConfig struct {
	Settings MonitorSettings `json:"settings"`
	Queries  []QueryConfig   `json:"queries"`
}

// MonitorSettings holds runtime parameters for the monitoring loop.
type MonitorSettings struct {
	CycleIntervalMinutes   int    `json:"cycle_interval_minutes"`
	QueriesPerCycle        int    `json:"queries_per_cycle"`
	PagesPerQuery          int    `json:"pages_per_query"`
	ResultsPerQuery        int    `json:"results_per_query"`
	PauseBetweenQueriesSec int    `json:"pause_between_queries_sec"`
	SaveReports            bool   `json:"save_reports"`
	SeenTweetsFile         string `json:"seen_tweets_file"`
	MaxSeenTweets          int    `json:"max_seen_tweets"`
	ReportDir              string `json:"report_dir"`
}
