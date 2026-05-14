package search

import (
	"fmt"
	"regexp"
	"strings"
	"time"
)

var tcoRe = regexp.MustCompile(`https://t\.co/\S+`)

// compactNumber formats an integer as a human-readable short string.
func compactNumber(n int) string {
	switch {
	case n >= 1_000_000:
		return fmt.Sprintf("%.1fM", float64(n)/1_000_000)
	case n >= 1_000:
		return fmt.Sprintf("%.1fK", float64(n)/1_000)
	default:
		return fmt.Sprintf("%d", n)
	}
}

// timeAgo returns a short human-readable relative time string.
func timeAgo(dateStr string) string {
	layouts := []string{
		time.RFC3339,
		"2006-01-02T15:04:05Z",
		"Mon Jan 02 15:04:05 -0700 2006", // Twitter legacy format
		"2006-01-02T15:04:05.000Z",
	}

	var t time.Time
	var err error
	for _, layout := range layouts {
		t, err = time.Parse(layout, dateStr)
		if err == nil {
			break
		}
	}
	if err != nil {
		return "?"
	}

	diff := time.Since(t)
	minutes := int(diff.Minutes())
	switch {
	case minutes < 60:
		return fmt.Sprintf("%dm", minutes)
	case minutes < 24*60:
		return fmt.Sprintf("%dh", minutes/60)
	default:
		return fmt.Sprintf("%dd", minutes/(24*60))
	}
}

// cleanText removes t.co links from text.
func cleanText(text string) string {
	return strings.TrimSpace(tcoRe.ReplaceAllString(text, ""))
}

// FormatTweetTelegram formats a single tweet for Telegram (HTML parse_mode).
func FormatTweetTelegram(t TweetData, index int) string {
	likes := compactNumber(t.Metrics.Likes)
	impressions := compactNumber(t.Metrics.Impressions)
	engagement := fmt.Sprintf("%sL %sI", likes, impressions)
	timeStr := timeAgo(t.CreatedAt)

	text := t.Text
	if len(text) > 200 {
		text = text[:197] + "..."
	}
	text = cleanText(text)

	var sb strings.Builder
	if index >= 0 {
		fmt.Fprintf(&sb, "%d. ", index+1)
	}
	fmt.Fprintf(&sb, "@%s (%s · %s)\n%s", t.Username, engagement, timeStr, text)

	if len(t.URLs) > 0 {
		fmt.Fprintf(&sb, "\n  %s", t.URLs[0])
	}
	fmt.Fprintf(&sb, "\n%s", t.TweetURL)

	return sb.String()
}

// FormatResultsTelegram formats a list of tweets for Telegram.
func FormatResultsTelegram(tweets []TweetData, query string, limit int) string {
	if limit <= 0 {
		limit = 15
	}

	shown := tweets
	if len(shown) > limit {
		shown = shown[:limit]
	}

	var sb strings.Builder
	if query != "" {
		fmt.Fprintf(&sb, "\"%s\" — %d results\n\n", query, len(tweets))
	}

	for i, t := range shown {
		if i > 0 {
			sb.WriteString("\n\n")
		}
		sb.WriteString(FormatTweetTelegram(t, i))
	}

	if len(tweets) > limit {
		fmt.Fprintf(&sb, "\n\n... +%d more", len(tweets)-limit)
	}
	return sb.String()
}

// FormatTweetMarkdown formats a single tweet as markdown for reports.
func FormatTweetMarkdown(t TweetData) string {
	engagement := fmt.Sprintf("%dL %dI", t.Metrics.Likes, t.Metrics.Impressions)
	text := cleanText(t.Text)
	quoted := strings.ReplaceAll(text, "\n", "\n  > ")

	out := fmt.Sprintf("- **@%s** (%s) [Tweet](%s)\n  > %s", t.Username, engagement, t.TweetURL, quoted)

	if len(t.URLs) > 0 {
		var links []string
		for _, u := range t.URLs {
			links = append(links, fmt.Sprintf("[link](%s)", u))
		}
		out += fmt.Sprintf("\n  Links: %s", strings.Join(links, ", "))
	}
	return out
}

// FormatResearchMarkdown formats a full research report as markdown.
func FormatResearchMarkdown(query string, tweets []TweetData) string {
	date := time.Now().Format("2006-01-02")

	var sb strings.Builder
	fmt.Fprintf(&sb, "# X Research: %s\n\n", query)
	fmt.Fprintf(&sb, "**Date:** %s\n", date)
	fmt.Fprintf(&sb, "**Tweets found:** %d\n\n", len(tweets))

	sb.WriteString("## Top Results (by engagement)\n\n")

	shown := tweets
	if len(shown) > 30 {
		shown = shown[:30]
	}
	for i, t := range shown {
		if i > 0 {
			sb.WriteString("\n\n")
		}
		sb.WriteString(FormatTweetMarkdown(t))
	}

	sb.WriteString("\n\n---\n\n## Research Metadata\n")
	fmt.Fprintf(&sb, "- **Query:** %s\n", query)
	fmt.Fprintf(&sb, "- **Date:** %s\n", date)
	fmt.Fprintf(&sb, "- **Tweets scanned:** %d\n", len(tweets))

	return sb.String()
}
