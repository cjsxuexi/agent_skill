package main

import (
	"regexp"
	"strings"
)

var (
	reOSC = regexp.MustCompile("\x1b\\][^\x07\x1b]*(?:\x07|\x1b\\\\)")
	reCSI = regexp.MustCompile("\x1b\\[[0-9:;<=>?]*[ -/]*[@-~]")
)

// cleanANSI removes terminal control sequences and resolves carriage returns
// and backspaces, returning printable text suitable for a plain-text dump.
func cleanANSI(s string) string {
	s = reOSC.ReplaceAllString(s, "")
	s = reCSI.ReplaceAllString(s, "")
	s = strings.ReplaceAll(s, "\x1b", "") // drop any stray ESC
	lines := strings.Split(s, "\n")
	for i, line := range lines {
		lines[i] = resolveLine(line)
	}
	return strings.Join(lines, "\n")
}

// resolveLine applies carriage-return overwrite and backspace within one line
// and drops remaining C0 control runes (keeping tab).
func resolveLine(line string) string {
	var buf []rune
	col := 0
	hadCR := false
	for _, r := range line {
		switch {
		case r == '\r':
			col = 0
			hadCR = true
		case r == '\b':
			if col > 0 {
				col--
			}
		case r < 0x20 && r != '\t':
			// drop other control chars (e.g. bell)
		default:
			if col < len(buf) {
				buf[col] = r
			} else {
				buf = append(buf, r)
			}
			col++
		}
	}
	// If no carriage return was used, trim to final column position.
	// If carriage return was used, keep all of the buffer.
	if !hadCR && col < len(buf) {
		buf = buf[:col]
	}
	return string(buf)
}
