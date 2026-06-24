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

// TestPairRoundsStartMarkerAnchorsRound1 locks the fix for startup echo
// contamination: when commands are pasted/piped before bash's first prompt is
// ready, the PTY echoes them as bare lines BEFORE the start-marker (seq 0).
// Round 1's region must begin AFTER marker 0, so those bare pre-prompt echoes
// are excluded and round 1's output is clean.
func TestPairRoundsStartMarkerAnchorsRound1(t *testing.T) {
	marker := "@@CMDCAP@@y"
	log := "" +
		"echo hello-world\n" + // pre-prompt bulk echo (noise, before marker 0)
		"ls /etc/hostname\n" + // more bulk echo noise
		marker + " 0\n" + // start-marker emitted at first prompt
		"user@host:~$ echo hello-world\n" + // real prompt+echo
		"hello-world\n" +
		marker + " 1\n" +
		"user@host:~$ ls /etc/hostname\n" +
		"/etc/hostname\n" +
		marker + " 2\n"
	rows := []indexRow{
		{Seq: 1, Cmd: "echo hello-world"},
		{Seq: 2, Cmd: "ls /etc/hostname"},
	}
	got := pairRounds(log, marker, rows)
	if len(got) != 2 {
		t.Fatalf("want 2 rounds, got %d", len(got))
	}
	if got[0].Output != "hello-world" {
		t.Errorf("round1 output = %q, want %q (pre-prompt echoes before marker 0 must be excluded)", got[0].Output, "hello-world")
	}
	if got[1].Output != "/etc/hostname" {
		t.Errorf("round2 output = %q", got[1].Output)
	}
}

// TestPairRoundsNoStartMarkerFallsBackToZero locks backward compatibility: a
// session without a "<marker> 0" line (e.g. recorded before the start-marker
// existed) must still pair rounds, with round 1's region falling back to the
// top of the log.
func TestPairRoundsNoStartMarkerFallsBackToZero(t *testing.T) {
	marker := "@@CMDCAP@@z"
	log := "" +
		"user@host:~$ pwd\n" +
		"/home/x\n" +
		marker + " 1\n" +
		"user@host:~$ id\n" +
		"uid=0\n" +
		marker + " 2\n"
	rows := []indexRow{
		{Seq: 1, Cmd: "pwd"},
		{Seq: 2, Cmd: "id"},
	}
	got := pairRounds(log, marker, rows)
	if len(got) != 2 {
		t.Fatalf("want 2 rounds, got %d", len(got))
	}
	if got[0].Output != "/home/x" {
		t.Errorf("round1 (no start marker) output = %q, want %q", got[0].Output, "/home/x")
	}
	if got[1].Output != "uid=0" {
		t.Errorf("round2 output = %q", got[1].Output)
	}
}

// TestPairRoundsOutputNoTrailingNewline documents the no-trailing-newline case
// (printf, echo -n, curl, JSON). Because _mark/_start print a LEADING newline,
// the marker always lands on its own line even when the preceding output has no
// trailing newline, so the round is recoverable. (The live gluing bug can only
// be reproduced end-to-end; this locks the pairRounds-side expectation.)
func TestPairRoundsOutputNoTrailingNewline(t *testing.T) {
	marker := "@@CMDCAP@@n"
	log := marker + " 0\n" +
		"user@host:~$ printf hello\n" +
		"hello\n" + // _mark's leading newline keeps the marker off this line
		marker + " 1\n" +
		"user@host:~$ echo next\n" +
		"next\n" +
		marker + " 2\n"
	rows := []indexRow{
		{Seq: 1, Cmd: "printf hello"},
		{Seq: 2, Cmd: "echo next"},
	}
	got := pairRounds(log, marker, rows)
	if len(got) != 2 {
		t.Fatalf("want 2 rounds, got %d", len(got))
	}
	if got[0].Output != "hello" {
		t.Errorf("round1 output = %q, want %q", got[0].Output, "hello")
	}
	if got[1].Output != "next" {
		t.Errorf("round2 output = %q", got[1].Output)
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

// TestSliceOutputFirstMatch locks in first-match: when an OUTPUT line ends with
// the command text (e.g. `history` echoes itself in its own output), the echo
// line is the FIRST occurrence and all output must be preserved. A last-match
// implementation would wrongly treat the trailing output line as the echo and
// drop everything before it.
func TestSliceOutputFirstMatch(t *testing.T) {
	region := []string{
		"user@host:~$ history",
		"  1  ls",
		"  2  history",
	}
	want := "  1  ls\n  2  history"
	if got := sliceOutput(region, "history"); got != want {
		t.Errorf("first-match slice = %q, want %q", got, want)
	}
}
