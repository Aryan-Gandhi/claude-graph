---
name: graph
description: Open a live browser page showing the current project's plan, orchestrator, subagents, and what needs the user's validation. Use when the user types /graph or asks to see agent/task progress visually.
---

# /graph

Show the user what is happening right now in a Chrome page. The page lives at
`~/.claude/graph/<slug>/index.html` and re-reads `state.js` every 2 seconds.

## Steps

1. **Pick the slug.** Run `python3 ~/.claude/skills/graph/hook.py --slug "$PWD"` and use what it prints.
   It is the folder name plus a short hash of the full path (for example `my-app-3fa9c1`), so two folders
   with the same name never share a page. Always use this command; do not build the slug by hand.

2. **Build the state from what you know right now.** Use the plan, your task list, and every subagent you have spawned
   this session (running or finished). Do not invent agents or steps. If there is no plan, derive steps from the user's
   current request and your task list.

3. **Write `~/.claude/graph/<slug>/state.json`** (create the directory first). If it already exists, read it and
   merge: a hook (`hook.py`) keeps it updated live with agents, their recent actions, and plan steps, so keep
   those and only add or fix what you know better (steps, `detail`, `evidence`, `review` status, `goal`).
   After writing, run `python3 ~/.claude/skills/graph/hook.py --render <slug>`; that regenerates `state.js`,
   which is what the page reads.

   Schema:

   ```json
   {
     "project": "my-app",
     "goal": "One sentence: what the user asked for",
     "updatedAt": "2026-11-05T19:40:00.000Z",
     "orchestrator": { "status": "running", "doing": "What the main agent is doing right now" },
     "steps": [
       { "id": "1", "title": "Short step title", "status": "done",
         "agent": "agent name or null", "note": "optional one line",
         "evidence": "only for status review: diff summary or test output",
         "detail": "optional short markdown shown on hover" }
     ],
     "agents": [
       { "id": "a1", "name": "short name", "type": "Explore | Plan | general-purpose | ...",
         "status": "running", "doing": "current action in one line", "stepId": "1",
         "startedAt": "ISO time", "finishedAt": "ISO time or null",
         "detail": "optional short markdown shown on hover" }
     ]
   }
   ```

   `detail` is the hover card. Keep it under ~8 lines of markdown: task, last few actions, files touched, what is next.
   Supported: `####` headings, `-` bullets, `**bold**`, `` `code` ``, fenced code blocks. If omitted, the card is built from the other fields.

   Fields the hook writes for you (leave them alone when merging): `lastEventAt` (drives the "quiet Xm / possibly
   stuck" warning), `actions` (last 6 tool calls), `result` (a subagent's final message), `waiting` and
   `waitingSince` (set when Claude asks for permission or input), `tid` (task id), and `autoDetail`.
   If you write your own `detail` for an agent and omit `autoDetail`, the hook keeps yours.

   Status values: `pending`, `running`, `done`, `blocked`, `review`, and `waiting` (agents only, set by the hook
   when Claude is waiting on the user in the CLI).
   `review` means finished by an agent and waiting for the user to validate; put proof in `evidence`.
   Set `updatedAt` to the current time (`date -u +%Y-%m-%dT%H:%M:%S.000Z`).

4. **Open the page:** `bash ~/.claude/skills/graph/open.sh <slug>`.
   It opens Chrome the first time and just refreshes the files after that. Pass `--force` as the second argument to reopen.

5. **Reply in two lines:** the URL, and one sentence on what the page shows right now (for example, "3 of 6 steps done, 2 agents running").

## Keeping it fresh

Once `/graph` has been run in a project, hooks in `~/.claude/settings.json` update `state.json` and `state.js`
automatically (prompt, before and after each tool call, subagent start/stop, TodoWrite, task events, notifications,
stop). The hook also copies the newest `index.html` into each opted-in project, so page updates reach old projects
too. Projects where `/graph` was never run are not touched. Note: `open.sh` uses macOS `open -a "Google Chrome"`. You only need to re-run `/graph` or edit `state.json` + `--render` for things
hooks can't know: `review` status with `evidence`, hand-written `detail`, a better `goal`.
