package main

import (
	"os"
	"strings"
)

type round struct {
	indexRow
	Output string
}

// extractRounds reads the session log, cleans it, and pairs each index row
// with its command output using the per-session marker lines as boundaries.
func extractRounds(s *session) ([]round, error) {
	rows, err := readIndex(s)
	if err != nil {
		return nil, err
	}
	raw, err := os.ReadFile(s.path("session.log"))
	if err != nil {
		return nil, err
	}
	return pairRounds(cleanANSI(string(raw)), s.marker(), rows), nil
}

// pairRounds is the pure core: given cleaned log text, the marker token, and
// index rows, it returns rounds with output sliced between marker lines.
func pairRounds(clean, marker string, rows []indexRow) []round {
	lines := strings.Split(clean, "\n")
	markerAt := map[int]int{}
	prefix := marker + " "
	for i, ln := range lines {
		if strings.HasPrefix(ln, prefix) {
			// seq 0 is the session start-marker (emitted at the first prompt);
			// it anchors round 1 so startup echo noise before it is excluded.
			if n := atoiSafe(strings.TrimSpace(ln[len(prefix):])); n >= 0 {
				markerAt[n] = i
			}
		}
	}
	var result []round
	for _, r := range rows {
		end, ok := markerAt[r.Seq]
		if !ok {
			continue // marker not found (e.g. log truncated mid-write)
		}
		start := 0
		if prev, ok := markerAt[r.Seq-1]; ok {
			start = prev + 1
		}
		out := sliceOutput(lines[start:end], r.Cmd)
		result = append(result, round{indexRow: r, Output: out})
	}
	return result
}

// sliceOutput drops the command-echo line from a region and returns the rest,
// trimmed of surrounding blank lines.
// We match the FIRST line whose right-trimmed text ends with the command: in an
// interactive session a round's region begins with the prompt+command echo, and
// the command's output follows. First-match is required for correctness — a
// command whose output contains a line ending in the command text (e.g.
// `history`, or `cat` of a file whose last line is the command) must keep that
// output, so we must not match a later occurrence.
func sliceOutput(region []string, cmd string) string {
	echoIdx := -1
	if cmd != "" {
		for i, ln := range region {
			if strings.HasSuffix(strings.TrimRight(ln, " "), cmd) {
				echoIdx = i
				break // first match is the echo line
			}
		}
	}
	var body []string
	switch {
	case echoIdx >= 0:
		body = region[echoIdx+1:]
	case len(region) > 0:
		body = region[1:] // fallback: drop first physical line
	}
	return strings.Trim(strings.Join(body, "\n"), "\n")
}

// atoiSafe parses a non-negative integer, returning -1 for empty or
// non-numeric input (so a literal "0" — the start-marker seq — is distinguished
// from a parse failure).
func atoiSafe(s string) int {
	if s == "" {
		return -1
	}
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return -1
		}
		n = n*10 + int(c-'0')
	}
	return n
}
