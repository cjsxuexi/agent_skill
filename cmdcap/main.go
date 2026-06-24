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
	case "_start":
		err = cmdStart(os.Args[2:])
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

