//go:build windows

package main

import "fmt"

func cmdShell(args []string) error {
	return fmt.Errorf("cmdcap shell is only supported on linux/unix targets")
}
