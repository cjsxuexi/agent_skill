package main

import (
	"encoding/base64"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type indexRow struct {
	Seq   int
	Epoch int64
	Exit  int
	Skip  bool
	Cwd   string
	Cmd   string
}

func b64(s string) string { return base64.StdEncoding.EncodeToString([]byte(s)) }

func unb64(s string) string {
	b, err := base64.StdEncoding.DecodeString(s)
	if err != nil {
		return ""
	}
	return string(b)
}

// cmdMark is the hidden subcommand invoked by the PROMPT_COMMAND hook:
//   cmdcap _mark <exit> <command...>
// It appends one index row and prints the round marker to stdout (the PTY),
// so the marker lands in session.log.
func cmdMark(args []string) error {
	dir := os.Getenv("CMDCAP_SESSION")
	if dir == "" {
		return nil // not in a recorded session; no-op
	}
	s, err := openSession(dir)
	if err != nil {
		return nil
	}
	exit := 0
	if len(args) > 0 {
		exit, _ = strconv.Atoi(args[0])
	}
	cmd := ""
	if len(args) > 1 {
		cmd = strings.Join(args[1:], " ")
	}
	cwd, _ := os.Getwd()
	seq := s.readInt("seq") + 1
	if err := s.writeInt("seq", seq); err != nil {
		return err
	}
	row := indexRow{Seq: seq, Epoch: time.Now().Unix(), Exit: exit, Skip: isCmdcapCommand(cmd), Cwd: cwd, Cmd: cmd}
	if err := appendIndexRow(s, row); err != nil {
		return err
	}
	// Leading newline is REQUIRED: if the command's output has no trailing
	// newline (printf, echo -n, curl, JSON, cat of a file without a final NL),
	// the PTY would otherwise glue this marker onto the last output line and
	// pairRounds could not find it, silently dropping the round.
	fmt.Printf("\n%s %d\n", s.marker(), seq) // -> terminal -> session.log
	return nil
}

// cmdStart is the hidden subcommand invoked once, by the PROMPT_COMMAND hook's
// first firing (at the first prompt). It prints the start-marker "<marker> 0" to
// stdout (the PTY -> session.log) so round 1's output region is anchored after
// it, excluding any startup echo noise that precedes the first real prompt.
func cmdStart(args []string) error {
	dir := os.Getenv("CMDCAP_SESSION")
	if dir == "" {
		return nil // not in a recorded session; no-op
	}
	s, err := openSession(dir)
	if err != nil {
		return nil
	}
	// Leading newline for the same reason as in cmdMark: keep the marker on its
	// own line regardless of preceding output.
	fmt.Printf("\n%s 0\n", s.marker())
	return nil
}

// isCmdcapCommand reports whether the command line invokes cmdcap itself
// (recorded as a boundary but excluded from saves).
func isCmdcapCommand(cmd string) bool {
	f := strings.Fields(cmd)
	if len(f) == 0 {
		return false
	}
	base := f[0]
	if i := strings.LastIndexAny(base, "/"); i >= 0 {
		base = base[i+1:]
	}
	return base == "cmdcap"
}

func appendIndexRow(s *session, r indexRow) error {
	f, err := os.OpenFile(s.path("index.tsv"), os.O_APPEND|os.O_WRONLY|os.O_CREATE, 0o600)
	if err != nil {
		return err
	}
	defer f.Close()
	skip := 0
	if r.Skip {
		skip = 1
	}
	_, err = fmt.Fprintf(f, "%d\t%d\t%d\t%d\t%s\t%s\n", r.Seq, r.Epoch, r.Exit, skip, b64(r.Cwd), b64(r.Cmd))
	return err
}

func readIndex(s *session) ([]indexRow, error) {
	b, err := os.ReadFile(s.path("index.tsv"))
	if err != nil {
		return nil, err
	}
	var rows []indexRow
	for _, line := range strings.Split(string(b), "\n") {
		line = strings.TrimRight(line, "\r")
		if line == "" {
			continue
		}
		parts := strings.Split(line, "\t")
		if len(parts) < 6 {
			continue
		}
		seq, _ := strconv.Atoi(parts[0])
		epoch, _ := strconv.ParseInt(parts[1], 10, 64)
		exit, _ := strconv.Atoi(parts[2])
		rows = append(rows, indexRow{
			Seq: seq, Epoch: epoch, Exit: exit, Skip: parts[3] == "1",
			Cwd: unb64(parts[4]), Cmd: unb64(parts[5]),
		})
	}
	return rows, nil
}
