#!/usr/bin/env python3
"""Dump the most recent Hermes agent session as a readable timeline.

Reads sessions out of the running container at /root/.hermes/sessions/.
Prints, for each turn: tool name + key arg (one line) or short agent text.
Highlights tool errors. Used by `make logs-session`.
"""

import json
import subprocess
import sys


CONTAINER = "hermes-cro-agent"
SESSIONS_DIR = "/root/.hermes/sessions"


def docker_exec(*cmd: str) -> str:
    r = subprocess.run(
        ["docker", "exec", CONTAINER, *cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        sys.stderr.write(f"docker exec failed: {r.stderr}\n")
        sys.exit(1)
    return r.stdout


def latest_session_path() -> str:
    listing = docker_exec("bash", "-lc",
                          f"ls -t {SESSIONS_DIR}/session_*.json 2>/dev/null | head -1").strip()
    if not listing:
        sys.stderr.write("no session files found in container\n")
        sys.exit(1)
    return listing


def copy_session(path: str) -> str:
    local = "/tmp/hermes-session-dump.json"
    subprocess.run(["docker", "cp", f"{CONTAINER}:{path}", local], check=True)
    return local


def short(s: str, n: int = 100) -> str:
    return s.replace("\n", " | ")[:n]


def parse_tool_output(raw: str) -> tuple[str, str]:
    """Return (status, summary) — flags errors so they stand out."""
    try:
        d = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ("ok", short(raw, 80))
    if d.get("success") is False or d.get("error"):
        err = d.get("error") or d.get("message") or str(d)
        return ("ERR", short(str(err), 80))
    # Pick a useful field for the summary
    for key in ("clicked", "url", "title", "result", "output"):
        if key in d:
            return ("ok", short(str(d[key]), 80))
    return ("ok", short(raw, 80))


def main() -> None:
    path = latest_session_path()
    local = copy_session(path)
    with open(local) as f:
        sess = json.load(f)

    msgs = sess.get("messages", [])
    print(f"=== session: {path.split('/')[-1]} ===")
    print(f"    model: {sess.get('model')}")
    print(f"    messages: {len(msgs)}")
    print()

    # Index assistant tool_use blocks by tool_use_id so we can pair them with
    # the next tool result. Hermes encodes tool calls as JSON inside assistant
    # string content for some models — we just print agent reasoning + tool
    # outputs in order.
    for i, m in enumerate(msgs):
        role = m.get("role")
        c = m.get("content", "")

        if role == "user" and isinstance(c, str):
            if i == 0 or "invoked the" in c[:100]:
                head = short(c, 120)
                print(f"{i:3d} START  {head}")
            continue

        if role == "assistant" and isinstance(c, str) and c.strip():
            print(f"{i:3d} THINK  {short(c, 140)}")
            continue

        if role == "tool" and isinstance(c, str):
            status, summary = parse_tool_output(c)
            tag = "TOOL ✗" if status == "ERR" else "TOOL  "
            print(f"{i:3d} {tag} {summary}")
            continue


if __name__ == "__main__":
    main()
