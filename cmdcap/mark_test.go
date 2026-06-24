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
