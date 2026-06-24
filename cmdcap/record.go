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
