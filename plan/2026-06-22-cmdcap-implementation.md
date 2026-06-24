# cmdcap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `cmdcap`, a single static Go binary that records a JumpServer target-machine shell session and writes clean, incremental command+output dumps the user downloads via Luna SFTP for Claude to read.

**Architecture:** `cmdcap shell` starts a recorded `bash` under a PTY; a `PROMPT_COMMAND` hook calls the hidden `cmdcap _mark` after every command to append an index row (seq, exit, cwd, command, skip-flag) and print a unique marker line into the typescript. `cmdcap save` cleans the typescript, slices each round's output between marker lines, pairs it with the indexed command, and writes only rounds past a persisted cursor (incremental). All output-parsing logic is pure and unit-tested on Windows; the PTY recorder is Linux-only and smoke-tested on a Linux host.

**Tech Stack:** Go 1.26 (`go1.26.4` confirmed on build host), `github.com/creack/pty` (PTY, pure-Go/static), `golang.org/x/term` (raw mode). Target runtime: linux/amd64 + bash + coreutils (already present). Build host: Windows.

## Global Constraints

- Target binary: `GOOS=linux GOARCH=amd64 CGO_ENABLED=0`, static, name `cmdcap`. Copy build flags verbatim: `-ldflags "-s -w"`.
- **Zero extra runtime deps on target** beyond `bash` (PROMPT_COMMAND/here-strings) and coreutils. No `script`/`col`/`sed`/`base64` invoked from shell — all parsing/encoding happens inside the Go binary.
- Subcommands & names are fixed: `cmdcap shell`, `cmdcap save`, `cmdcap status`, `cmdcap version`, hidden `cmdcap _mark`.
- `save` default behavior is **incremental** via a persisted `cursor` (watermark); it must never re-emit rounds at or below the cursor.
- Commands whose first word resolves to `cmdcap` are recorded as boundaries (`skip=1`) but **excluded** from saves.
- Project root: `D:\jk_file\skills\cmdcap\` (Go module `cmdcap`). Built binary: `D:\jk_file\skills\cmdcap\dist\cmdcap-linux-amd64`. Local inbox convention: `D:\wiki\cmdcap-inbox\`.
- Go package layout: single flat `package main` in the module root; pure logic in their own files with `_test.go` siblings; the PTY recorder is `//go:build !windows`-gated with a Windows stub.

---

## File Structure

| File | Responsibility |
|---|---|
| `go.mod` | Module `cmdcap`, Go 1.26, deps creack/pty + x/term |
| `main.go` | Arg dispatch, usage, `version` |
| `session.go` | Session dir lifecycle, int-file helpers (seq/cursor), marker, session resolution |
| `mark.go` | `indexRow` type, base64 helpers, `cmdcap _mark`, index read/write, cmdcap-self detection |
| `clean.go` | `cleanANSI` — strip CSI/OSC/ESC, resolve CR/BS, drop stray C0 (pure) |
| `extract.go` | `extractRounds`/`pairRounds`/`sliceOutput` — slice typescript into rounds (pure) |
| `save.go` | Flag parse, round selection (default/-n/range/tail), dump format, `cmdcap save`, `cmdcap status` |
| `record.go` | `//go:build !windows` — `cmdcap shell` PTY recorder |
| `record_other.go` | `//go:build windows` — `cmdShell` stub |
| `rcfile.go` | Generate the temp bash rcfile with the PROMPT_COMMAND hook |
| `*_test.go` | Unit tests for clean/extract/mark/save selection |
| `README.md` | Install, usage, known limits |
| `dist/cmdcap-linux-amd64` | Cross-compiled artifact |

---

## Task 1: Scaffold + dispatch + version

**Files:**
- Create: `D:\jk_file\skills\cmdcap\go.mod`
- Create: `D:\jk_file\skills\cmdcap\main.go`

**Interfaces:**
- Produces: `func main()`, `const version`; subcommand functions referenced (defined in later tasks): `cmdShell`, `cmdSave`, `cmdStatus`, `cmdMark`. Until those exist this task uses temporary stubs that are REPLACED (not duplicated) by later tasks.

- [ ] **Step 1: Create the module**

Run in `D:\jk_file\skills\cmdcap\`:
```powershell
go mod init cmdcap
```
Then set the Go line in `go.mod` to:
```
module cmdcap

go 1.26
```

- [ ] **Step 2: Write `main.go` with dispatch + temporary stubs**

```go
package main

import (
	"fmt"
	"os"
)

const version = "0.1.0"

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	var err error
	switch os.Args[1] {
	case "shell":
		err = cmdShell(os.Args[2:])
	case "save":
		err = cmdSave(os.Args[2:])
	case "status":
		err = cmdStatus(os.Args[2:])
	case "_mark":
		err = cmdMark(os.Args[2:])
	case "version", "-v", "--version":
		fmt.Println("cmdcap", version)
	default:
		usage()
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "cmdcap:", err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, `cmdcap — capture command+output rounds for JumpServer sessions

usage:
  cmdcap shell                 start a recorded subshell (run once per session)
  cmdcap save [flags]          write new rounds to ~/cmdcap-out/, then advance cursor
  cmdcap status                show session id, rounds, cursor
  cmdcap version

save flags:
  -n N             last N rounds (instead of since-last-save)
  --from A --to B  explicit round range (does not move the cursor)
  --tail M         keep only the last M output lines per round
  -o PATH          output file path`)
}

// --- temporary stubs, replaced by later tasks ---

func cmdShell(args []string) error  { return fmt.Errorf("not implemented") }
func cmdSave(args []string) error   { return fmt.Errorf("not implemented") }
func cmdStatus(args []string) error { return fmt.Errorf("not implemented") }
func cmdMark(args []string) error   { return fmt.Errorf("not implemented") }
```

- [ ] **Step 3: Verify it builds and runs**

Run:
```powershell
go build ./... ; go run . version
```
Expected: build succeeds; prints `cmdcap 0.1.0`.

- [ ] **Step 4: Commit**

```bash
cd /d/jk_file/skills/cmdcap && git init -q 2>/dev/null; git add -A && git commit -q -m "feat(cmdcap): scaffold module, dispatch, version"
```
(If `D:\wiki\scripts` is already a git repo, skip `git init`. If it is not and you do not want a repo here, skip the commit and note it — the deliverable is the built binary regardless.)

---

## Task 2: ANSI / control cleaning (`clean.go`)

**Files:**
- Create: `D:\jk_file\skills\cmdcap\clean.go`
- Test: `D:\jk_file\skills\cmdcap\clean_test.go`

**Interfaces:**
- Produces: `func cleanANSI(s string) string` — removes terminal escapes, resolves `\r`/`\b` per line, drops stray C0 control bytes except `\t`/`\n`. Used by `extract.go` (Task 4).

- [ ] **Step 1: Write the failing tests**

`clean_test.go`:
```go
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
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := cleanANSI(c.in); got != c.want {
				t.Errorf("cleanANSI(%q) = %q, want %q", c.in, got, c.want)
			}
		})
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
go test . -run TestCleanANSI -v
```
Expected: FAIL — `undefined: cleanANSI`.

- [ ] **Step 3: Implement `clean.go`**

```go
package main

import (
	"regexp"
	"strings"
)

var (
	reOSC = regexp.MustCompile("\x1b\\][^\x07\x1b]*(?:\x07|\x1b\\\\)")
	reCSI = regexp.MustCompile("\x1b\\[[0-9;?]*[ -/]*[@-~]")
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
	for _, r := range line {
		switch {
		case r == '\r':
			col = 0
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
	return string(buf)
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
go test . -run TestCleanANSI -v
```
Expected: PASS (all subtests).

- [ ] **Step 5: Commit**

```bash
cd /d/jk_file/skills/cmdcap && git add clean.go clean_test.go && git commit -q -m "feat(cmdcap): ANSI/control cleaning"
```

---

## Task 3: Session state + index + `_mark`

**Files:**
- Create: `D:\jk_file\skills\cmdcap\session.go`
- Create: `D:\jk_file\skills\cmdcap\mark.go`
- Test: `D:\jk_file\skills\cmdcap\mark_test.go`
- Modify: `D:\jk_file\skills\cmdcap\main.go` (remove the temporary `cmdMark` stub)

**Interfaces:**
- Produces:
  - `type session struct { dir string }`
  - `func newSession(id string) (*session, error)`, `func openSession(dir string) (*session, error)`, `func latestSession() (*session, error)`, `func resolveSession() (*session, error)`
  - `func homeDir() string`, `func cmdcapRoot() string`
  - methods: `(*session) path(name string) string`, `(*session) readInt(name string) int`, `(*session) writeInt(name string, n int) error`, `(*session) marker() string`
  - `type indexRow struct { Seq int; Epoch int64; Exit int; Skip bool; Cwd string; Cmd string }`
  - `func appendIndexRow(s *session, r indexRow) error`, `func readIndex(s *session) ([]indexRow, error)`
  - `func isCmdcapCommand(cmd string) bool`
  - `func cmdMark(args []string) error` (replaces stub)
- Consumes: nothing from later tasks.

- [ ] **Step 1: Write the failing tests**

`mark_test.go`:
```go
package main

import "testing"

func TestIsCmdcapCommand(t *testing.T) {
	yes := []string{"cmdcap save", "cmdcap", "/home/x/cmdcap save", "./cmdcap status", "cmdcap   -n 3"}
	no := []string{"ls -la", "kubectl get pods", "echo cmdcap", "VAR=1 cmdcap", "cat cmdcap.log"}
	for _, c := range yes {
		if !isCmdcapCommand(c) {
			t.Errorf("isCmdcapCommand(%q) = false, want true", c)
		}
	}
	for _, c := range no {
		if isCmdcapCommand(c) {
			t.Errorf("isCmdcapCommand(%q) = true, want false", c)
		}
	}
}

func TestMarkAppendsRowAndPrintsMarker(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("HOME", dir)            // homeDir() -> dir
	t.Setenv("USERPROFILE", dir)     // windows home
	s, err := newSession("testsess")
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("CMDCAP_SESSION", s.dir)

	// run two real commands and one cmdcap command
	if err := cmdMark([]string{"0", "ls", "-la"}); err != nil {
		t.Fatal(err)
	}
	if err := cmdMark([]string{"2", "false"}); err != nil {
		t.Fatal(err)
	}
	if err := cmdMark([]string{"0", "cmdcap", "save"}); err != nil {
		t.Fatal(err)
	}

	rows, err := readIndex(s)
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 3 {
		t.Fatalf("want 3 rows, got %d", len(rows))
	}
	if rows[0].Seq != 1 || rows[0].Cmd != "ls -la" || rows[0].Exit != 0 || rows[0].Skip {
		t.Errorf("row0 wrong: %+v", rows[0])
	}
	if rows[1].Seq != 2 || rows[1].Cmd != "false" || rows[1].Exit != 2 {
		t.Errorf("row1 wrong: %+v", rows[1])
	}
	if rows[2].Seq != 3 || !rows[2].Skip {
		t.Errorf("row2 should be skip=true: %+v", rows[2])
	}
	if got := s.readInt("seq"); got != 3 {
		t.Errorf("seq = %d, want 3", got)
	}
}

func TestMarkNoSessionIsNoop(t *testing.T) {
	t.Setenv("CMDCAP_SESSION", "")
	if err := cmdMark([]string{"0", "ls"}); err != nil {
		t.Errorf("expected nil error when no session, got %v", err)
	}
}

func TestReadIntDefaultsZero(t *testing.T) {
	dir := t.TempDir()
	s := &session{dir: dir}
	if got := s.readInt("missing"); got != 0 {
		t.Errorf("readInt(missing) = %d, want 0", got)
	}
	if err := s.writeInt("cursor", 7); err != nil {
		t.Fatal(err)
	}
	if got := s.readInt("cursor"); got != 7 {
		t.Errorf("cursor = %d, want 7", got)
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
go test . -run "TestIsCmdcapCommand|TestMark|TestReadInt" -v
```
Expected: FAIL — undefined identifiers (`isCmdcapCommand`, `newSession`, etc.). (Also a duplicate-`cmdMark` error once Step 4 lands — resolved in Step 5.)

- [ ] **Step 3: Implement `session.go`**

```go
package main

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type session struct {
	dir string
}

func homeDir() string {
	h, _ := os.UserHomeDir()
	return h
}

func cmdcapRoot() string { return filepath.Join(homeDir(), ".cmdcap") }

func newSession(id string) (*session, error) {
	dir := filepath.Join(cmdcapRoot(), id)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	s := &session{dir: dir}
	if err := os.WriteFile(s.path("index.tsv"), nil, 0o600); err != nil {
		return nil, err
	}
	if err := s.writeInt("seq", 0); err != nil {
		return nil, err
	}
	if err := s.writeInt("cursor", 0); err != nil {
		return nil, err
	}
	mk := make([]byte, 8)
	if _, err := rand.Read(mk); err != nil {
		return nil, err
	}
	marker := "@@CMDCAP@@" + hex.EncodeToString(mk)
	if err := os.WriteFile(s.path("marker"), []byte(marker), 0o600); err != nil {
		return nil, err
	}
	return s, nil
}

func openSession(dir string) (*session, error) {
	if dir == "" {
		return nil, errors.New("no active session (set CMDCAP_SESSION or run `cmdcap shell` first)")
	}
	if _, err := os.Stat(dir); err != nil {
		return nil, fmt.Errorf("session dir not found: %s", dir)
	}
	return &session{dir: dir}, nil
}

func latestSession() (*session, error) {
	entries, err := os.ReadDir(cmdcapRoot())
	if err != nil {
		return nil, errors.New("no sessions found; run `cmdcap shell` first")
	}
	var dirs []os.DirEntry
	for _, e := range entries {
		if e.IsDir() {
			dirs = append(dirs, e)
		}
	}
	if len(dirs) == 0 {
		return nil, errors.New("no sessions found; run `cmdcap shell` first")
	}
	sort.Slice(dirs, func(i, j int) bool {
		fi, _ := dirs[i].Info()
		fj, _ := dirs[j].Info()
		return fi.ModTime().After(fj.ModTime())
	})
	return &session{dir: filepath.Join(cmdcapRoot(), dirs[0].Name())}, nil
}

func resolveSession() (*session, error) {
	if dir := os.Getenv("CMDCAP_SESSION"); dir != "" {
		return openSession(dir)
	}
	return latestSession()
}

func (s *session) path(name string) string { return filepath.Join(s.dir, name) }

func (s *session) readInt(name string) int {
	b, err := os.ReadFile(s.path(name))
	if err != nil {
		return 0
	}
	n, _ := strconv.Atoi(strings.TrimSpace(string(b)))
	return n
}

func (s *session) writeInt(name string, n int) error {
	return os.WriteFile(s.path(name), []byte(strconv.Itoa(n)), 0o600)
}

func (s *session) marker() string {
	b, _ := os.ReadFile(s.path("marker"))
	return strings.TrimSpace(string(b))
}
```

- [ ] **Step 4: Implement `mark.go`**

```go
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
	fmt.Printf("%s %d\n", s.marker(), seq) // -> terminal -> session.log
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
```

- [ ] **Step 5: Remove the temporary `cmdMark` stub in `main.go`**

Delete this line from the stub block in `main.go`:
```go
func cmdMark(args []string) error   { return fmt.Errorf("not implemented") }
```
(Leave the `cmdShell`, `cmdSave`, `cmdStatus` stubs; they are replaced in later tasks.)

- [ ] **Step 6: Run tests to verify they pass**

Run:
```powershell
go test . -run "TestIsCmdcapCommand|TestMark|TestReadInt" -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /d/jk_file/skills/cmdcap && git add session.go mark.go mark_test.go main.go && git commit -q -m "feat(cmdcap): session state, index, _mark hook"
```

---

## Task 4: Round extraction (`extract.go`)

**Files:**
- Create: `D:\jk_file\skills\cmdcap\extract.go`
- Test: `D:\jk_file\skills\cmdcap\extract_test.go`

**Interfaces:**
- Consumes: `cleanANSI` (Task 2), `indexRow`/`readIndex` (Task 3), `(*session).marker`/`path` (Task 3).
- Produces:
  - `type round struct { indexRow; Output string }`
  - `func extractRounds(s *session) ([]round, error)` — reads `session.log`, cleans, pairs.
  - `func pairRounds(clean, marker string, rows []indexRow) []round` — pure core.
  - `func sliceOutput(region []string, cmd string) string`

- [ ] **Step 1: Write the failing tests**

`extract_test.go`:
```go
package main

import "testing"

func TestPairRounds(t *testing.T) {
	marker := "@@CMDCAP@@abcd"
	// Simulated cleaned typescript:
	//   prompt+cmd echo, output, marker, ... repeated. Round 3 is a cmdcap save (skip).
	log := "" +
		"user@host:~$ ls\n" +
		"file1\nfile2\n" +
		marker + " 1\n" +
		"user@host:~$ echo hi\n" +
		"hi\n" +
		marker + " 2\n" +
		"user@host:~$ cmdcap save\n" +
		"saved...\n" +
		marker + " 3\n"
	rows := []indexRow{
		{Seq: 1, Cmd: "ls", Exit: 0},
		{Seq: 2, Cmd: "echo hi", Exit: 0},
		{Seq: 3, Cmd: "cmdcap save", Exit: 0, Skip: true},
	}
	got := pairRounds(log, marker, rows)
	if len(got) != 3 {
		t.Fatalf("want 3 rounds, got %d", len(got))
	}
	if got[0].Seq != 1 || got[0].Output != "file1\nfile2" {
		t.Errorf("round1 output = %q", got[0].Output)
	}
	if got[1].Seq != 2 || got[1].Output != "hi" {
		t.Errorf("round2 output = %q", got[1].Output)
	}
	if got[2].Seq != 3 || !got[2].Skip || got[2].Output != "saved..." {
		t.Errorf("round3 = %+v", got[2])
	}
}

func TestPairRoundsMissingMarkerSkipped(t *testing.T) {
	marker := "@@CMDCAP@@x"
	log := "p$ ls\nout\n" + marker + " 1\n" // only marker 1 present
	rows := []indexRow{{Seq: 1, Cmd: "ls"}, {Seq: 2, Cmd: "pwd"}}
	got := pairRounds(log, marker, rows)
	if len(got) != 1 || got[0].Seq != 1 {
		t.Fatalf("want only round 1, got %+v", got)
	}
}

func TestSliceOutputFallback(t *testing.T) {
	// command echo not matchable -> fallback drops first physical line
	region := []string{"weird-prompt-line", "out-a", "out-b"}
	if got := sliceOutput(region, "no-such-cmd"); got != "out-a\nout-b" {
		t.Errorf("fallback slice = %q", got)
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
go test . -run "TestPairRounds|TestSliceOutput" -v
```
Expected: FAIL — `undefined: pairRounds` / `sliceOutput`.

- [ ] **Step 3: Implement `extract.go`**

```go
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
			if n := atoiSafe(strings.TrimSpace(ln[len(prefix):])); n > 0 {
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
func sliceOutput(region []string, cmd string) string {
	echoIdx := -1
	for i, ln := range region {
		if cmd != "" && strings.HasSuffix(strings.TrimRight(ln, " "), cmd) {
			echoIdx = i
			break
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

func atoiSafe(s string) int {
	if s == "" {
		return 0
	}
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return 0
		}
		n = n*10 + int(c-'0')
	}
	return n
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
go test . -run "TestPairRounds|TestSliceOutput" -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /d/jk_file/skills/cmdcap && git add extract.go extract_test.go && git commit -q -m "feat(cmdcap): round extraction from typescript"
```

---

## Task 5: `save` + `status`

**Files:**
- Create: `D:\jk_file\skills\cmdcap\save.go`
- Test: `D:\jk_file\skills\cmdcap\save_test.go`
- Modify: `D:\jk_file\skills\cmdcap\main.go` (remove temporary `cmdSave` and `cmdStatus` stubs)

**Interfaces:**
- Consumes: `round`/`extractRounds` (Task 4), `resolveSession`/`readIndex`/`(*session).readInt`/`writeInt` (Task 3), `homeDir` (Task 3).
- Produces:
  - `type saveOpts struct { n, from, to, tail int; out string }`
  - `func parseSaveArgs(args []string) (saveOpts, error)`
  - `func selectRounds(all []round, cursor int, o saveOpts) (sel []round, advanceTo int, advance bool)`
  - `func applyTail(out string, tail int) string`
  - `func formatDump(s *session, sel []round, tail int) string`
  - `func cmdSave(args []string) error`, `func cmdStatus(args []string) error` (replace stubs)

- [ ] **Step 1: Write the failing tests**

`save_test.go`:
```go
package main

import (
	"strings"
	"testing"
)

func mkRounds(specs ...struct {
	seq  int
	skip bool
}) []round {
	var rs []round
	for _, sp := range specs {
		rs = append(rs, round{indexRow: indexRow{Seq: sp.seq, Skip: sp.skip, Cmd: "c"}, Output: "o"})
	}
	return rs
}

func seqs(rs []round) []int {
	var out []int
	for _, r := range rs {
		out = append(out, r.Seq)
	}
	return out
}

func TestSelectDefaultIncremental(t *testing.T) {
	all := mkRounds(
		struct {
			seq  int
			skip bool
		}{1, false},
		struct {
			seq  int
			skip bool
		}{2, false},
		struct {
			seq  int
			skip bool
		}{3, true}, // a cmdcap command
		struct {
			seq  int
			skip bool
		}{4, false},
	)
	sel, adv, advance := selectRounds(all, 2, saveOpts{})
	if !advance || adv != 4 {
		t.Fatalf("advance=%v advanceTo=%d, want true/4", advance, adv)
	}
	if got := seqs(sel); len(got) != 1 || got[0] != 4 {
		t.Fatalf("selected %v, want [4] (skip 3, skip <=cursor)", got)
	}
}

func TestSelectDefaultNothingNew(t *testing.T) {
	all := mkRounds(struct {
		seq  int
		skip bool
	}{1, false})
	sel, _, _ := selectRounds(all, 1, saveOpts{})
	if len(sel) != 0 {
		t.Fatalf("want nothing new, got %v", seqs(sel))
	}
}

func TestSelectLastN(t *testing.T) {
	all := mkRounds(
		struct {
			seq  int
			skip bool
		}{1, false},
		struct {
			seq  int
			skip bool
		}{2, false},
		struct {
			seq  int
			skip bool
		}{3, false},
	)
	sel, adv, advance := selectRounds(all, 0, saveOpts{n: 2})
	if got := seqs(sel); len(got) != 2 || got[0] != 2 || got[1] != 3 {
		t.Fatalf("selected %v, want [2 3]", got)
	}
	if !advance || adv != 3 {
		t.Fatalf("advance=%v to=%d, want true/3", advance, adv)
	}
}

func TestSelectExplicitRangeNoAdvance(t *testing.T) {
	all := mkRounds(
		struct {
			seq  int
			skip bool
		}{1, false},
		struct {
			seq  int
			skip bool
		}{2, false},
		struct {
			seq  int
			skip bool
		}{3, false},
	)
	sel, _, advance := selectRounds(all, 0, saveOpts{from: 1, to: 2})
	if advance {
		t.Fatal("explicit range must not advance cursor")
	}
	if got := seqs(sel); len(got) != 2 || got[0] != 1 || got[1] != 2 {
		t.Fatalf("selected %v, want [1 2]", got)
	}
}

func TestApplyTail(t *testing.T) {
	if got := applyTail("a\nb\nc\nd", 2); got != "c\nd" {
		t.Errorf("applyTail = %q, want %q", got, "c\nd")
	}
	if got := applyTail("a\nb", 0); got != "a\nb" {
		t.Errorf("applyTail(0) should be no-op, got %q", got)
	}
}

func TestParseSaveArgs(t *testing.T) {
	o, err := parseSaveArgs([]string{"-n", "3", "--tail", "50", "-o", "/tmp/x.txt"})
	if err != nil {
		t.Fatal(err)
	}
	if o.n != 3 || o.tail != 50 || o.out != "/tmp/x.txt" {
		t.Errorf("parsed %+v", o)
	}
	if _, err := parseSaveArgs([]string{"--bogus"}); err == nil {
		t.Error("expected error on unknown flag")
	}
}

func TestFormatDumpHasHeaderAndRounds(t *testing.T) {
	s := &session{dir: "/x/.cmdcap/sess1"}
	sel := []round{{indexRow: indexRow{Seq: 5, Cmd: "ls -la", Exit: 0, Cwd: "/home/x", Epoch: 1750000000}, Output: "file1\nfile2"}}
	dump := formatDump(s, sel, 0)
	for _, want := range []string{"# cmdcap dump", "rounds=5-5", "[#5] $ ls -la", "exit=0", "file1\nfile2"} {
		if !strings.Contains(dump, want) {
			t.Errorf("dump missing %q\n---\n%s", want, dump)
		}
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
go test . -run "TestSelect|TestApplyTail|TestParseSaveArgs|TestFormatDump" -v
```
Expected: FAIL — undefined `selectRounds`/`parseSaveArgs`/etc.

- [ ] **Step 3: Implement `save.go`**

```go
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type saveOpts struct {
	n    int // -n N (0 = unset)
	from int // --from (0 = unset)
	to   int // --to (0 = unset)
	tail int // --tail M (0 = unset)
	out  string
}

func parseSaveArgs(args []string) (saveOpts, error) {
	var o saveOpts
	need := func(i int, name string) (int, error) {
		if i >= len(args) {
			return 0, fmt.Errorf("%s needs a value", name)
		}
		return strconv.Atoi(args[i])
	}
	for i := 0; i < len(args); i++ {
		var err error
		switch args[i] {
		case "-n":
			i++
			o.n, err = need(i, "-n")
		case "--from":
			i++
			o.from, err = need(i, "--from")
		case "--to":
			i++
			o.to, err = need(i, "--to")
		case "--tail":
			i++
			o.tail, err = need(i, "--tail")
		case "-o":
			i++
			if i >= len(args) {
				return o, fmt.Errorf("-o needs a path")
			}
			o.out = args[i]
		default:
			return o, fmt.Errorf("unknown flag: %s", args[i])
		}
		if err != nil {
			return o, err
		}
	}
	return o, nil
}

// selectRounds chooses which rounds to emit and whether to advance the cursor.
func selectRounds(all []round, cursor int, o saveOpts) (sel []round, advanceTo int, advance bool) {
	var emit []round
	maxSeq := 0
	for _, r := range all {
		if r.Seq > maxSeq {
			maxSeq = r.Seq
		}
		if !r.Skip {
			emit = append(emit, r)
		}
	}
	switch {
	case o.from > 0 || o.to > 0:
		lo, hi := o.from, o.to
		if hi == 0 {
			hi = maxSeq
		}
		for _, r := range emit {
			if r.Seq >= lo && r.Seq <= hi {
				sel = append(sel, r)
			}
		}
		return sel, 0, false // explicit range never advances cursor
	case o.n > 0:
		if o.n < len(emit) {
			emit = emit[len(emit)-o.n:]
		}
		return emit, maxSeq, true
	default:
		for _, r := range emit {
			if r.Seq > cursor {
				sel = append(sel, r)
			}
		}
		return sel, maxSeq, true
	}
}

func applyTail(out string, tail int) string {
	if tail <= 0 {
		return out
	}
	lines := strings.Split(out, "\n")
	if len(lines) <= tail {
		return out
	}
	return strings.Join(lines[len(lines)-tail:], "\n")
}

const dumpBar = "================================================================"
const dumpSub = "----------------------------------------------------------------"

func formatDump(s *session, sel []round, tail int) string {
	var b strings.Builder
	host, _ := os.Hostname()
	user := os.Getenv("USER")
	if user == "" {
		user = os.Getenv("USERNAME")
	}
	lo, hi := 0, 0
	if len(sel) > 0 {
		lo, hi = sel[0].Seq, sel[len(sel)-1].Seq
	}
	fmt.Fprintf(&b, "# cmdcap dump\n")
	fmt.Fprintf(&b, "host=%s user=%s session=%s saved=%s rounds=%d-%d\n",
		host, user, filepath.Base(s.dir), time.Now().Format("2006-01-02 15:04:05"), lo, hi)
	for _, r := range sel {
		b.WriteString(dumpBar + "\n")
		fmt.Fprintf(&b, "[#%d] $ %s    (exit=%d  cwd=%s  %s)\n",
			r.Seq, r.Cmd, r.Exit, r.Cwd, time.Unix(r.Epoch, 0).Format("2006-01-02 15:04:05"))
		b.WriteString(dumpSub + "\n")
		b.WriteString(applyTail(r.Output, tail))
		b.WriteString("\n\n")
	}
	return b.String()
}

func cmdSave(args []string) error {
	o, err := parseSaveArgs(args)
	if err != nil {
		return err
	}
	s, err := resolveSession()
	if err != nil {
		return err
	}
	rounds, err := extractRounds(s)
	if err != nil {
		return err
	}
	cursor := s.readInt("cursor")
	sel, advanceTo, advance := selectRounds(rounds, cursor, o)
	if len(sel) == 0 {
		fmt.Println("cmdcap: no new rounds to save")
		return nil
	}
	content := formatDump(s, sel, o.tail)
	outPath := o.out
	if outPath == "" {
		outDir := filepath.Join(homeDir(), "cmdcap-out")
		if err := os.MkdirAll(outDir, 0o700); err != nil {
			return err
		}
		outPath = filepath.Join(outDir, fmt.Sprintf("cap-%d-%d-%d.txt", time.Now().Unix(), sel[0].Seq, sel[len(sel)-1].Seq))
	}
	if err := os.WriteFile(outPath, []byte(content), 0o600); err != nil {
		return err
	}
	if advance {
		_ = s.writeInt("cursor", advanceTo)
	}
	fmt.Printf("已保存 %d 轮 (#%d-#%d) → %s\n", len(sel), sel[0].Seq, sel[len(sel)-1].Seq, outPath)
	fmt.Printf("请用 Luna 下载该文件到 D:\\wiki\\cmdcap-inbox\\\n")
	return nil
}

func cmdStatus(args []string) error {
	s, err := resolveSession()
	if err != nil {
		return err
	}
	rows, err := readIndex(s)
	if err != nil {
		return err
	}
	cursor := s.readInt("cursor")
	total, saveable, unsaved := 0, 0, 0
	for _, r := range rows {
		total++
		if !r.Skip {
			saveable++
			if r.Seq > cursor {
				unsaved++
			}
		}
	}
	fmt.Printf("session=%s\nrounds: total=%d saveable=%d unsaved=%d\ncursor=%d\n",
		filepath.Base(s.dir), total, saveable, unsaved, cursor)
	return nil
}
```

- [ ] **Step 4: Remove the temporary `cmdSave`/`cmdStatus` stubs in `main.go`**

Delete these lines from the stub block in `main.go`:
```go
func cmdSave(args []string) error   { return fmt.Errorf("not implemented") }
func cmdStatus(args []string) error { return fmt.Errorf("not implemented") }
```
(Only `cmdShell` stub remains; Task 6 replaces it via build-gated files.)

- [ ] **Step 5: Run tests + full build to verify they pass**

Run:
```powershell
go test . -run "TestSelect|TestApplyTail|TestParseSaveArgs|TestFormatDump" -v ; go build ./...
```
Expected: PASS; build succeeds.

- [ ] **Step 6: Commit**

```bash
cd /d/jk_file/skills/cmdcap && git add save.go save_test.go main.go && git commit -q -m "feat(cmdcap): save (incremental/range/tail) and status"
```

---

## Task 6: PTY recorder (`cmdcap shell`) + rcfile

**Files:**
- Create: `D:\jk_file\skills\cmdcap\record.go` (`//go:build !windows`)
- Create: `D:\jk_file\skills\cmdcap\record_other.go` (`//go:build windows`)
- Create: `D:\jk_file\skills\cmdcap\rcfile.go`
- Test: `D:\jk_file\skills\cmdcap\rcfile_test.go`
- Modify: `D:\jk_file\skills\cmdcap\main.go` (remove the last temporary `cmdShell` stub)
- Modify: `D:\jk_file\skills\cmdcap\go.mod` / `go.sum` (add deps)

**Interfaces:**
- Consumes: `newSession`/`(*session).dir`/`path`/`readInt` (Task 3).
- Produces: `func cmdShell(args []string) error` (both build variants); `func writeRcfile(s *session, binDir, binPath string) (string, error)`.

- [ ] **Step 1: Add dependencies**

Run in `D:\jk_file\skills\cmdcap\` (needs network once; modules are compiled into the static binary, not a runtime dep):
```powershell
go get github.com/creack/pty@latest ; go get golang.org/x/term@latest
```
Expected: `go.mod` now requires both; `go.sum` written.

- [ ] **Step 2: Write the failing test (rcfile generation — pure, runs on Windows)**

`rcfile_test.go`:
```go
package main

import (
	"os"
	"strings"
	"testing"
)

func TestWriteRcfile(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("HOME", dir)
	t.Setenv("USERPROFILE", dir)
	s, err := newSession("rcsess")
	if err != nil {
		t.Fatal(err)
	}
	rc, err := writeRcfile(s, "/opt/bin", "/opt/bin/cmdcap")
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove(rc)
	b, err := os.ReadFile(rc)
	if err != nil {
		t.Fatal(err)
	}
	body := string(b)
	for _, want := range []string{
		`export CMDCAP_SESSION=`,
		`_mark "$ec" "$cmd"`,
		`history 1`,
		`__cmdcap_prompt`,
		`/opt/bin/cmdcap`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("rcfile missing %q\n---\n%s", want, body)
		}
	}
	// must initialize last-num so the first PROMPT_COMMAND doesn't record stale history
	if !strings.Contains(body, "__CMDCAP_LAST_NUM") {
		t.Error("rcfile must initialize __CMDCAP_LAST_NUM")
	}
}
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```powershell
go test . -run TestWriteRcfile -v
```
Expected: FAIL — `undefined: writeRcfile`.

- [ ] **Step 4: Implement `rcfile.go`**

```go
package main

import (
	"fmt"
	"os"
	"path/filepath"
)

// writeRcfile creates the temp bash rcfile that sources the user's rc, puts the
// cmdcap binary on PATH, and installs the PROMPT_COMMAND hook calling `_mark`.
func writeRcfile(s *session, binDir, binPath string) (string, error) {
	content := fmt.Sprintf(`# cmdcap session rcfile (auto-generated; safe to delete)
[ -f /etc/bash.bashrc ] && . /etc/bash.bashrc
[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"
export PATH=%q:"$PATH"
export CMDCAP_SESSION=%q
__CMDCAP_BIN=%q
__cmdcap_prompt() {
  local ec=$?
  local line num cmd
  line=$(HISTTIMEFORMAT='' history 1)
  read -r num cmd <<< "$line"
  if [ "$num" != "$__CMDCAP_LAST_NUM" ]; then
    __CMDCAP_LAST_NUM="$num"
    "$__CMDCAP_BIN" _mark "$ec" "$cmd"
  fi
}
{ line=$(HISTTIMEFORMAT='' history 1); read -r __CMDCAP_LAST_NUM _ <<< "$line"; }
case "$PROMPT_COMMAND" in
  *__cmdcap_prompt*) ;;
  *) PROMPT_COMMAND="__cmdcap_prompt${PROMPT_COMMAND:+; $PROMPT_COMMAND}" ;;
esac
`, binDir, s.dir, binPath)

	f, err := os.CreateTemp(filepath.Dir(s.dir), "cmdcap-rc-*.sh")
	if err != nil {
		return "", err
	}
	if _, err := f.WriteString(content); err != nil {
		f.Close()
		return "", err
	}
	if err := f.Close(); err != nil {
		return "", err
	}
	return f.Name(), nil
}
```

- [ ] **Step 5: Implement `record.go` (Linux) and `record_other.go` (Windows stub)**

`record.go`:
```go
//go:build !windows

package main

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/creack/pty"
	"golang.org/x/term"
)

func cmdShell(args []string) error {
	if os.Getenv("CMDCAP_SESSION") != "" {
		return fmt.Errorf("already inside a cmdcap session (%s); type `exit` first", os.Getenv("CMDCAP_SESSION"))
	}
	bash, err := exec.LookPath("bash")
	if err != nil {
		return fmt.Errorf("bash not found on PATH; cmdcap shell requires bash")
	}
	self, err := os.Executable()
	if err != nil {
		return err
	}
	self, _ = filepath.Abs(self)
	binDir := filepath.Dir(self)

	id := fmt.Sprintf("%d-%d", time.Now().Unix(), os.Getpid())
	s, err := newSession(id)
	if err != nil {
		return err
	}
	rcPath, err := writeRcfile(s, binDir, self)
	if err != nil {
		return err
	}
	defer os.Remove(rcPath)

	cmd := exec.Command(bash, "--rcfile", rcPath, "-i")
	cmd.Env = append(os.Environ(), "CMDCAP_SESSION="+s.dir)

	ptmx, err := pty.Start(cmd)
	if err != nil {
		return err
	}
	defer func() { _ = ptmx.Close() }()

	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGWINCH)
	go func() {
		for range ch {
			_ = pty.InheritSize(os.Stdin, ptmx)
		}
	}()
	defer signal.Stop(ch)
	_ = pty.InheritSize(os.Stdin, ptmx) // initial size

	if old, err := term.MakeRaw(int(os.Stdin.Fd())); err == nil {
		defer term.Restore(int(os.Stdin.Fd()), old)
	}

	logFile, err := os.OpenFile(s.path("session.log"), os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o600)
	if err != nil {
		return err
	}
	defer logFile.Close()

	go func() { _, _ = io.Copy(ptmx, os.Stdin) }()
	_, _ = io.Copy(io.MultiWriter(os.Stdout, logFile), ptmx)

	fmt.Fprintf(os.Stderr, "\r\ncmdcap: session ended (%d rounds recorded). Use `cmdcap save`.\r\n", s.readInt("seq"))
	return nil
}
```

`record_other.go`:
```go
//go:build windows

package main

import "fmt"

func cmdShell(args []string) error {
	return fmt.Errorf("cmdcap shell is only supported on linux/unix targets")
}
```

- [ ] **Step 6: Remove the last temporary `cmdShell` stub in `main.go`**

Delete from `main.go`:
```go
func cmdShell(args []string) error  { return fmt.Errorf("not implemented") }
```
Also remove the now-unused `"fmt"` import from `main.go` ONLY if nothing else uses it — `main.go` still uses `fmt.Println`/`fmt.Fprintln`, so keep the import. (Verify with the build in Step 7.)

- [ ] **Step 7: Verify Windows build + all unit tests still pass**

Run:
```powershell
go build ./... ; go test . -v
```
Expected: build succeeds (Windows uses `record_other.go`); all tests PASS.

- [ ] **Step 8: Verify the Linux binary cross-compiles**

Run:
```powershell
$env:GOOS="linux"; $env:GOARCH="amd64"; $env:CGO_ENABLED="0"; go build -ldflags "-s -w" -o dist/cmdcap-linux-amd64 . ; Remove-Item Env:GOOS,Env:GOARCH,Env:CGO_ENABLED
```
Expected: `dist/cmdcap-linux-amd64` produced, no errors.

- [ ] **Step 9: Commit**

```bash
cd /d/jk_file/skills/cmdcap && git add record.go record_other.go rcfile.go rcfile_test.go main.go go.mod go.sum && git commit -q -m "feat(cmdcap): PTY recorder, rcfile hook, windows stub"
```

---

## Task 7: Cross-compile artifact, README, end-to-end verification

**Files:**
- Create: `D:\jk_file\skills\cmdcap\README.md`
- Create/refresh: `D:\jk_file\skills\cmdcap\dist\cmdcap-linux-amd64`
- Create (local convention dir): `D:\wiki\cmdcap-inbox\` (with a `.keep` file)

**Interfaces:** none (delivery + docs + verification).

- [ ] **Step 1: Produce the release binary**

Run:
```powershell
$env:GOOS="linux"; $env:GOARCH="amd64"; $env:CGO_ENABLED="0"; go build -ldflags "-s -w" -o dist/cmdcap-linux-amd64 . ; Remove-Item Env:GOOS,Env:GOARCH,Env:CGO_ENABLED
```
Then confirm it is an ELF and statically linked:
```powershell
Get-Item dist/cmdcap-linux-amd64 | Select-Object Length
```
Expected: a multi-MB file exists. (ELF/static is implied by `CGO_ENABLED=0` + `GOOS=linux`.)

- [ ] **Step 2: Create the inbox dir**

```powershell
New-Item -ItemType Directory -Force D:\wiki\cmdcap-inbox | Out-Null ; New-Item -ItemType File -Force D:\wiki\cmdcap-inbox\.keep | Out-Null
```

- [ ] **Step 3: Write `README.md`**

```markdown
# cmdcap — JumpServer 命令/输出捕获

把 JumpServer (Luna Web 终端) 目标机上的「命令+输出」按轮次存成干净文本，
经 Luna SFTP 下载到本地 `D:\wiki\cmdcap-inbox\`，供 Claude 读取。

## 安装（每台目标机一次）

1. Luna 文件管理 → 上传 `cmdcap-linux-amd64` 到目标机 `~/`。
2. 在目标机终端：
   ```
   mv ~/cmdcap-linux-amd64 ~/cmdcap && chmod +x ~/cmdcap
   ```
   之后用 `~/cmdcap` 调用（或 `export PATH="$HOME:$PATH"` 后直接 `cmdcap`）。

## 每次使用

1. 进会话后开录：
   ```
   ~/cmdcap shell
   ```
   进入一个被录制的子 shell（照常敲命令，`cd`/管道/builtin 均正常；
   子 shell 内 `cmdcap` 已在 PATH）。
2. 正常执行 Claude 给的命令。想取回结果时，单独一行执行：
   ```
   cmdcap save
   ```
   它把上次保存之后的新轮次写成 `~/cmdcap-out/cap-<ts>-<from>-<to>.txt` 并打印路径。
3. Luna 下载该文件到 `D:\wiki\cmdcap-inbox\`，告诉 Claude「读最新的」。
4. 结束：`exit`。

## save 选项

| 命令 | 含义 |
|---|---|
| `cmdcap save` | 增量：上次保存之后的新轮次（默认，不重复） |
| `cmdcap save -n 3` | 最近 3 轮 |
| `cmdcap save --from 5 --to 7` | 指定区间（补取旧内容；不移动游标） |
| `cmdcap save --tail 100` | 每轮只保留末尾 100 行 |
| `cmdcap status` | 看会话、轮次数、游标 |

## 约定（Claude 发命令时）

诊断命令各占一行，最后单独一行 `cmdcap save`。不要写 `cmd ; cmdcap save`
同行（会并成一条 history、污染命令文本与输出）。

## 边界

- 面向行式诊断命令（ps/cat/tail/curl/kubectl get/看日志）。
- 全屏 TUI（vim/top/交互式 less）刷屏，去 ANSI 后仍乱，不适合捕获。
- `save` 不重跑命令、无副作用。
- 需目标机有 `bash`；每条命令后终端会多出一行明文标记（切片用，可接受）。
- 每次保存需在 Luna 手动下载一次（堡垒机隔离的固有代价）。
```

- [ ] **Step 4: End-to-end smoke test (Linux)**

Pick whichever is available, in order of preference:

**Option A — WSL on the build host:**
```bash
wsl -e bash -lc '
set -e
cp /mnt/d/jk_file/skills/cmdcap/dist/cmdcap-linux-amd64 /tmp/cmdcap && chmod +x /tmp/cmdcap
cd /tmp
# drive the recorded shell non-interactively via a here-doc of commands
printf "echo hello-world\nls /etc/hostname\ncmdcap save\nexit\n" | CMDCAP_SESSION= /tmp/cmdcap shell
ls -t ~/cmdcap-out | head -1
cat ~/cmdcap-out/$(ls -t ~/cmdcap-out | head -1)
'
```
Expected: the dumped file contains a `[#1] $ echo hello-world` round with `hello-world` output and a `[#2] $ ls /etc/hostname` round; the `cmdcap save` round is absent (skipped).

**Option B — a reachable Linux dev host** (the user SSHes to `192.168.3.x` hosts): `scp dist/cmdcap-linux-amd64` there, run the same `printf ... | ~/cmdcap shell` sequence, `cat` the newest dump. Confirm with the user before touching a shared host.

**Option C — manual:** hand the binary to the user to run `~/cmdcap shell`, a couple of commands, `cmdcap save`, and paste back the dump for inspection.

If the smoke test reveals slicing glitches (e.g., the command-echo line leaking into output because of an unusual `PS1`), note it and adjust `sliceOutput`'s echo-matching — do not mark the task done until a real dump looks clean.

- [ ] **Step 5: Commit**

```bash
cd /d/jk_file/skills/cmdcap && git add README.md dist/cmdcap-linux-amd64 && git commit -q -m "chore(cmdcap): linux/amd64 artifact + README"
```

---

## Self-Review

**1. Spec coverage**

| Spec (§) | Task |
|---|---|
| §4.1 session state files | Task 3 (`newSession`) |
| §4.2 `cmdcap shell` PTY record | Task 6 |
| §4.3 PROMPT_COMMAND hook, skip-filter, marker | Task 3 (`_mark`, `isCmdcapCommand`) + Task 6 (`rcfile`) |
| §4.4 output slicing + ANSI clean | Task 2 (`cleanANSI`) + Task 4 (`pairRounds`/`sliceOutput`) |
| §4.5 `save` default/-n/range/tail, cursor, file format | Task 5 |
| §4.6 `status`/`version` | Task 1 (`version`) + Task 5 (`status`) |
| §5 local inbox/source layout | Task 7 |
| §6 install/build | Task 6 Step 8, Task 7 |
| §7 limitations | Task 7 README |

No gaps.

**2. Placeholder scan:** No TBD/TODO; every code step has full source; every test step has assertions. The only non-code "fill-in" is Task 7 Step 4 offering three smoke-test environments — that is an intentional environment branch, not a placeholder, and each branch is fully specified.

**3. Type consistency:** `session`, `indexRow`, `round`, `saveOpts` field names and method names (`path`, `readInt`, `writeInt`, `marker`, `appendIndexRow`, `readIndex`, `extractRounds`, `pairRounds`, `sliceOutput`, `selectRounds`, `parseSaveArgs`, `applyTail`, `formatDump`) are used identically across tasks. Stub functions in `main.go` (Task 1) are explicitly removed in Tasks 3/5/6 so there are no duplicate definitions at completion. `cmdShell` exists in exactly one of `record.go`/`record_other.go` per platform via build tags.

> Note: the temporary stubs in Task 1 keep the module compiling between tasks; if implementing out of order, ensure exactly one definition of each `cmd*` exists before building.
