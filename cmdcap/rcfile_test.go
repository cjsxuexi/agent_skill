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
		`export PATH=`,
		`/etc/bash.bashrc`,
		`"$HOME/.bashrc"`,
		`_start`, // first prompt emits the start-marker that anchors round 1
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
