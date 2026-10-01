"""Stop a quicklook process and every child it started."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def spawn(command: list[str], cwd: Path | str | None = None) -> subprocess.Popen[bytes]:
    """Start a command array. On Linux the process leads its own group."""
    cwd_str = str(cwd) if cwd is not None else None
    if os.name == "nt":
        return subprocess.Popen(command, cwd=cwd_str)
    return subprocess.Popen(command, cwd=cwd_str, start_new_session=True)


def kill_tree(pid: int) -> None:
    """Kill the process tree. Windows uses taskkill; Linux signals the group."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            check=False,
            capture_output=True,
        )
        return
    killpg = getattr(os, "killpg", None)
    sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
    if not callable(killpg):
        return
    try:
        killpg(pid, sigkill)
    except OSError:
        return


def pid_alive(pid: int) -> bool:
    """Return whether the operating system still has this process."""
    if os.name == "nt":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
        )
        return f'"{pid}"' in completed.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
