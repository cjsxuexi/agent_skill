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
