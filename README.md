# claude-graph

A `/graph` slash command for Claude Code that opens a live browser page showing the plan, the main agent, each subagent, what it is doing right now, quiet/stuck warnings, and when it is waiting for you. It is a read-only viewer, and it uses no tokens because the hooks are local scripts.

This is an early version.

## Files

- `SKILL.md`: the skill definition that makes `/graph` available in Claude Code.
- `hook.py`: the local hook script that records Claude Code events into the project's state folder.
- `index.html`: the live browser page that renders the recorded state.
- `open.sh`: opens the page in Google Chrome.

## Install

1. Copy these files into `~/.claude/skills/graph/`.
2. Add hook entries to `~/.claude/settings.json` for the events `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `Notification` and `Stop`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks":[{"type":"command","command":"python3 ~/.claude/skills/graph/hook.py","async":true}]}],
    "PreToolUse":       [{"hooks":[{"type":"command","command":"python3 ~/.claude/skills/graph/hook.py","async":true}]}],
    "PostToolUse":      [{"hooks":[{"type":"command","command":"python3 ~/.claude/skills/graph/hook.py","async":true}]}],
    "SubagentStart":    [{"hooks":[{"type":"command","command":"python3 ~/.claude/skills/graph/hook.py","async":true}]}],
    "SubagentStop":     [{"hooks":[{"type":"command","command":"python3 ~/.claude/skills/graph/hook.py","async":true}]}],
    "TaskCreated":      [{"hooks":[{"type":"command","command":"python3 ~/.claude/skills/graph/hook.py","async":true}]}],
    "TaskCompleted":    [{"hooks":[{"type":"command","command":"python3 ~/.claude/skills/graph/hook.py","async":true}]}],
    "Notification":     [{"hooks":[{"type":"command","command":"python3 ~/.claude/skills/graph/hook.py","async":true}]}],
    "Stop":             [{"hooks":[{"type":"command","command":"python3 ~/.claude/skills/graph/hook.py","async":true}]}]
  }
}
```

If you already have a `hooks` section, merge these entries into it.

3. Restart Claude Code, then type `/graph` in a project.

## Notes

- macOS and Chrome only: `open.sh` uses `open -a "Google Chrome"`.
- Needs `python3`.
- The hook does nothing in a project until `/graph` has been run there once.
- State lives in `~/.claude/graph/<project>/`.
