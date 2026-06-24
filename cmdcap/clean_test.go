package main

import "testing"

func TestCleanANSI(t *testing.T) {
	cases := []struct{ name, in, want string }{
		{"csi color", "\x1b[31mred\x1b[0m", "red"},
		{"csi cursor", "abc\x1b[2Kdef", "abcdef"},
		{"osc title bel", "\x1b]0;my title\x07hello", "hello"},
		{"osc title st", "\x1b]0;t\x1b\\hello", "hello"},
		{"carriage return overwrite", "100%\rdone", "done"},
		{"partial cr overwrite", "abcdef\rXYZ", "XYZdef"},
		{"backspace", "abc\b\bX", "aX"},
		{"bell dropped", "ding\x07dong", "dingdong"},
		{"keep tab and newline", "a\tb\nc", "a\tb\nc"},
		{"plain passthrough", "just text", "just text"},
		{"csi sgr mouse", "before\x1b[<0;1;2Mafter", "beforeafter"},
		{"csi secondary da", "\x1b[>0cwait", "wait"},
		{"csi colon subparams", "\x1b[38:5:1mtext\x1b[0m", "text"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := cleanANSI(c.in); got != c.want {
				t.Errorf("cleanANSI(%q) = %q, want %q", c.in, got, c.want)
			}
		})
	}
}
