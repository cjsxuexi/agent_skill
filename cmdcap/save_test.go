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
