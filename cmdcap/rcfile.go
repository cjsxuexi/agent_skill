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
__CMDCAP_FIRST=1
__cmdcap_prompt() {
  local ec=$?
  local line num cmd
  line=$(HISTTIMEFORMAT='' history 1)
  read -r num cmd <<< "$line"
  # First firing happens at the first prompt, before any user command. Seed the
  # history watermark and emit the start-marker (anchors round 1); do not record.
  if [ "$__CMDCAP_FIRST" = "1" ]; then
    __CMDCAP_FIRST=0
    __CMDCAP_LAST_NUM="$num"
    "$__CMDCAP_BIN" _start
    return
  fi
  if [ "$num" != "$__CMDCAP_LAST_NUM" ]; then
    __CMDCAP_LAST_NUM="$num"
    "$__CMDCAP_BIN" _mark "$ec" "$cmd"
  fi
}
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
