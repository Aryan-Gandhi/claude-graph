#!/usr/bin/env python3
"""Claude Code hook -> keeps ~/.claude/graph/<slug>/state.json + state.js fresh.

Opt-in per project: does nothing unless /graph has been run there once
(i.e. ~/.claude/graph/<slug>/index.html exists). Never prints, never blocks.

Usage:
  hook.py              read hook JSON on stdin, apply the event
  hook.py --slug DIR   print the slug used for project directory DIR
  hook.py --render S   rebuild state.js from state.json for slug S (used by /graph)
"""
import fcntl, hashlib, json, os, re, shutil, sys, tempfile
from datetime import datetime, timezone

ROOT = os.path.expanduser("~/.claude/graph")
SKILL_PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
MAX_ACTIONS = 6
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def slugify(path):
    """folder name + short hash of the full path, so ~/a/app and ~/b/app never share a page"""
    full = os.path.realpath(path)
    base = re.sub(r"[^a-z0-9]+", "-", os.path.basename(full.rstrip("/")).lower()).strip("-") or "project"
    return "%s-%s" % (base[:40], hashlib.sha1(full.encode()).hexdigest()[:6])


def clip(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def describe(tool, inp):
    inp = inp if isinstance(inp, dict) else {}
    if tool == "Bash":
        return "Bash: " + clip(inp.get("command"), 70)
    if tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        return "%s: %s" % (tool, os.path.basename(str(inp.get("file_path") or inp.get("notebook_path") or "")))
    if tool in ("Grep", "Glob"):
        return "%s: %s" % (tool, clip(inp.get("pattern"), 50))
    if tool in ("Agent", "Task"):
        return "Spawning " + clip(inp.get("subagent_type") or inp.get("description") or "agent", 40)
    if tool == "TodoWrite":
        return "Updating plan"
    return clip(tool, 40) or "tool"


def agent_detail(a):
    lines = []
    if a.get("type"):
        lines.append("- **Type:** `%s`" % a["type"])
    acts = a.get("actions") or []
    if acts:
        lines.append("\n#### Last actions")
        lines += ["- " + str(x).replace("`", "'") for x in acts[-MAX_ACTIONS:]]
    if a.get("result"):
        lines.append("\n#### Result\n" + str(a["result"]))
    return "\n".join(lines)


def set_detail(a):
    """auto-build the hover text, but never overwrite one that was written by hand"""
    if a.get("detail") and not a.get("autoDetail"):
        return
    a["detail"] = agent_detail(a)
    a["autoDetail"] = True


def load(path):
    """Read state.json. A corrupt file is kept as .bak instead of being silently wiped."""
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except FileNotFoundError:
        data = {}
    except Exception:
        try:
            os.replace(path, path + ".bak")
        except Exception:
            pass
        data = {}
    for k in ("agents", "steps"):
        v = data.get(k)
        data[k] = [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []
    if not isinstance(data.get("orchestrator"), dict):
        data["orchestrator"] = {"status": "running", "doing": ""}
    return data


def save(d, state):
    state["updatedAt"] = now()
    # state.json first, state.js last: the page reads state.js, so it never sees a half-written update
    for name, text in (
        ("state.json", json.dumps(state, indent=1)),
        ("state.js", "window.GRAPH_STATE = " + json.dumps(state) + ";\n"),
    ):
        fd, tmp = tempfile.mkstemp(dir=d)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(text)
            os.chmod(tmp, 0o644)
            os.replace(tmp, os.path.join(d, name))
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise


def find_agent(state, aid):
    if not aid:
        return None
    for a in state["agents"]:
        if a.get("id") == aid:
            return a
    return None


def apply(ev, p, state):
    orch = state["orchestrator"]
    aid = p.get("agent_id")
    ag = find_agent(state, aid)

    # activity timestamps feed the page's "quiet for Xm" warning
    if ev != "Notification":
        t = now()
        orch["lastEventAt"] = t
        if ag:
            ag["lastEventAt"] = t
        # any real activity means whoever was waiting for the user has been unblocked
        for x in [orch] + ([ag] if ag else []):
            if x.get("status") == "waiting":
                x["status"] = "running"
                x.pop("waiting", None)
                x.pop("waitingSince", None)

    if ev == "UserPromptSubmit":
        orch.update(status="running", doing="Working on your request")
        prompt = str(p.get("prompt") or "")
        if not state.get("goal") and prompt and not prompt.startswith("/"):
            state["goal"] = clip(prompt, 160)

    elif ev == "Stop":
        orch.update(status="done", doing="Finished, waiting for you")

    elif ev == "SubagentStart":
        if not aid:
            return False
        if not ag:
            ag = {"id": aid, "actions": []}
            state["agents"].append(ag)
        atype = str(p.get("agent_type") or "agent")
        ag.update(name=atype, type=atype, status="running", doing="Starting up",
                  startedAt=now(), finishedAt=None, lastEventAt=now())
        set_detail(ag)

    elif ev == "SubagentStop":
        if not ag:
            return False
        msg = clip(p.get("last_assistant_message"), 280)
        ag.update(status="done", finishedAt=now(), doing=clip(msg, 110) or "Finished", result=msg)
        set_detail(ag)

    elif ev in ("PreToolUse", "PostToolUse"):
        pre = ev == "PreToolUse"
        tool, inp = p.get("tool_name"), p.get("tool_input")
        if not pre and tool == "TodoWrite" and isinstance(inp, dict) and isinstance(inp.get("todos"), list):
            try:
                old = {s.get("title"): s for s in state["steps"]}
                m = {"completed": "done", "in_progress": "running", "pending": "pending"}
                steps = []
                for t in inp["todos"]:
                    if not isinstance(t, dict):
                        continue
                    i = len(steps) + 1
                    title = clip(t.get("content") or t.get("activeForm") or "Step %d" % i, 120)
                    s = dict(old.get(title, {}))
                    s.update(id=str(i), title=title, status=m.get(t.get("status"), "pending"))
                    steps.append(s)
                state["steps"] = steps
            except Exception:
                pass  # a bad todo list must not lose the rest of this event
        desc = describe(tool, inp)
        if ag:
            acts = ag.setdefault("actions", [])
            running = desc + " (running)"
            if pre:
                acts.append(running)
            elif acts and acts[-1] == running:
                acts[-1] = desc  # same call finished: replace, don't duplicate
            else:
                acts.append(desc)
            del acts[:-MAX_ACTIONS]
            ag["doing"] = ("Running " + desc) if pre else desc
            set_detail(ag)
        else:
            orch["doing"] = ("Running " + desc) if pre else desc
            orch["status"] = "running"

    elif ev == "Notification":
        # Claude is asking for permission or input: flag the agent (or main agent) as waiting for the user
        tgt = ag or orch
        tgt["status"] = "waiting"
        tgt["waiting"] = clip(p.get("message"), 160) or "Needs your attention in the CLI"
        tgt["waitingSince"] = now()

    elif ev in ("TaskCreated", "TaskCompleted"):
        tid = str(p.get("task_id") or "")
        subject = clip(p.get("task_subject"), 100)
        steps = state["steps"]
        s = next((x for x in steps if tid and x.get("tid") == tid), None)
        if not s and ev == "TaskCompleted" and subject:
            s = next((x for x in steps if x.get("title") == subject), None)
        if not s:
            s = {"id": tid or str(len(steps) + 1), "tid": tid, "title": subject or "Task", "status": "pending"}
            steps.append(s)
        if ev == "TaskCompleted":
            s["status"] = "done"
    else:
        return False
    return True


def refresh_page(d):
    """keep each project's page in step with the skill's newest index.html"""
    try:
        dst = os.path.join(d, "index.html")
        if os.path.getmtime(SKILL_PAGE) > os.path.getmtime(dst):
            shutil.copyfile(SKILL_PAGE, dst)
    except Exception:
        pass


def locked(d):
    lk = open(os.path.join(d, ".lock"), "a")
    fcntl.flock(lk, fcntl.LOCK_EX)
    return lk


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--slug":
        print(slugify(args[1]))
        return
    if len(args) >= 2 and args[0] == "--render":
        slug = args[1]
        d = os.path.join(ROOT, slug)
        if not SLUG_RE.match(slug) or not os.path.isdir(d):
            return
        with locked(d):
            st = load(os.path.join(d, "state.json"))
            save(d, st)
        return

    try:
        p = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(p, dict):
        return
    slug = slugify(p.get("cwd") or os.getcwd())
    d = os.path.join(ROOT, slug)
    if not os.path.isfile(os.path.join(d, "index.html")):
        return  # not opted in for this project
    refresh_page(d)
    with locked(d):
        state = load(os.path.join(d, "state.json"))
        state.setdefault("project", slug.rsplit("-", 1)[0])
        if apply(p.get("hook_event_name"), p, state):
            save(d, state)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a hook must never break the session
    sys.exit(0)
