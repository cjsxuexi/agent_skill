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
	warnUnsliced(s, rounds)
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
	fmt.Printf("请用 Luna 下载该文件到本地收件箱(交给 Claude 读最新)\n")
	return nil
}

// warnUnsliced turns silent round loss into a visible warning: if a non-skip
// command was recorded in the index but its output could not be sliced from the
// typescript (no matching marker found), tell the user instead of dropping it
// quietly — silent loss is the worst failure mode for a capture tool.
func warnUnsliced(s *session, rounds []round) {
	rows, err := readIndex(s)
	if err != nil {
		return
	}
	recovered := map[int]bool{}
	for _, r := range rounds {
		recovered[r.Seq] = true
	}
	var missing []int
	for _, r := range rows {
		if !r.Skip && !recovered[r.Seq] {
			missing = append(missing, r.Seq)
		}
	}
	if len(missing) > 0 {
		fmt.Fprintf(os.Stderr, "cmdcap: warning: %d command(s) could not be sliced from the log and were skipped: #%v\n", len(missing), missing)
	}
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
