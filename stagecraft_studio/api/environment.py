"""Machine checks for the environment page. The page only displays this report."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from stagecraft_studio.api.models import EnvCheck, EnvironmentReport
from stagecraft_studio.api.steps import EngineIdentity
from stagecraft_studio.engine.launch import EngineLaunch

_MEMORY_FLOOR = 8 * 1024**3
_DISK_FLOOR = 10 * 1024**3
REQUIRED_R_PACKAGES: tuple[str, ...] = ("jsonlite", "Matrix", "limma", "edgeR", "DESeq2")
_R_PKG_PROBE = (
    "pkgs <- c('jsonlite','Matrix','limma','edgeR','DESeq2'); "
    "miss <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)]; "
    "cat(paste(miss, collapse=','))"
)


def collect_environment(launch: EngineLaunch, identity: EngineIdentity) -> EnvironmentReport:
    """Probe the engine interpreter, R, R packages, version, memory, and free disk."""
    r_program = _resolve_rscript()
    r_ver = _r_version(r_program)
    missing_r = _missing_r_packages(r_program) if r_ver else ()
    return environment_report(
        python_version=_python_version(launch.python),
        r_version=r_ver,
        engine_version=identity.version,
        engine_name=identity.name,
        memory_bytes=_memory_bytes(),
        disk_free_bytes=shutil.disk_usage(tempfile.gettempdir()).free,
        missing_r_packages=missing_r,
    )


def environment_report(
    *,
    python_version: str | None,
    r_version: str | None,
    engine_version: str,
    engine_name: str,
    memory_bytes: int | None,
    disk_free_bytes: int | None,
    missing_r_packages: tuple[str, ...] = (),
) -> EnvironmentReport:
    """Turn probe results into pass or fail rows. Thresholds live only here."""
    checks = [
        _python(python_version),
        _r(r_version, missing_r_packages),
        _engine(engine_name, engine_version),
        _memory(memory_bytes),
        _disk(disk_free_bytes),
    ]
    return EnvironmentReport(checks=checks)


def _python(version: str | None) -> EnvCheck:
    if version:
        return _ok("python", f"Python {version}", "")
    return _bad("python", "解释器没有返回版本。", "检查启动 Studio 时配置的引擎 Python 能否运行。")


def _r(version: str | None, missing_packages: tuple[str, ...] = ()) -> EnvCheck:
    if not version:
        return _bad("r", "没有找到 Rscript。", "安装 R，或设置 STAGECRAFT_RSCRIPT 指向 Rscript。")
    if missing_packages:
        shown = "、".join(missing_packages)
        return _bad(
            "r",
            f"{version}（缺少 R 包：{shown}）",
            f"在当前 R 环境中安装缺失包：{', '.join(missing_packages)}。",
        )
    return _ok("r", version, "")


def _engine(name: str, version: str) -> EnvCheck:
    if version:
        return _ok("engine", f"{name} {version}", "")
    return _bad(
        "engine",
        "没有读到引擎版本。",
        "确认 run_pipeline.py 上一级目录有 pyproject.toml。",
    )


def _memory(amount: int | None) -> EnvCheck:
    if amount is not None and amount >= _MEMORY_FLOOR:
        return _ok("memory", f"可用内存 {_gib(amount)} GB", "")
    shown = "读不到" if amount is None else f"{_gib(amount)} GB"
    return _bad("memory", f"可用内存 {shown}。", "可用内存需要至少 8 GB。关掉其他程序后再检查。")


def _disk(amount: int | None) -> EnvCheck:
    if amount is not None and amount >= _DISK_FLOOR:
        return _ok("disk", f"剩余磁盘 {_gib(amount)} GB", "")
    shown = "读不到" if amount is None else f"{_gib(amount)} GB"
    return _bad("disk", f"剩余磁盘 {shown}。", "请至少留出 10 GB 空闲空间。")


def _ok(name: str, detail: str, fix: str) -> EnvCheck:
    return EnvCheck(name=name, status="pass", label="通过", detail=detail, fix=fix)


def _bad(name: str, detail: str, fix: str) -> EnvCheck:
    return EnvCheck(name=name, status="fail", label="不通过", detail=detail, fix=fix)


def _gib(amount: int) -> str:
    return f"{amount / 1024**3:.1f}"


def _python_version(python: Path) -> str | None:
    if not python.is_file():
        return None
    try:
        completed = subprocess.run(
            [str(python), "-c", "import sys; print(sys.version.split()[0])"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    text = completed.stdout.strip()
    return text or None


def _resolve_rscript() -> str | None:
    return os.environ.get("STAGECRAFT_RSCRIPT", "").strip() or shutil.which("Rscript")


def _r_version(program: str | None = None) -> str | None:
    resolved = program if program is not None else _resolve_rscript()
    if not resolved:
        return None
    try:
        completed = subprocess.run(
            [resolved, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    text = (completed.stderr or completed.stdout).strip().splitlines()
    return text[0] if text else resolved


def _missing_r_packages(program: str | None) -> tuple[str, ...]:
    if not program:
        return ()
    try:
        completed = subprocess.run(
            [program, "--vanilla", "-e", _R_PKG_PROBE],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return REQUIRED_R_PACKAGES
    if completed.returncode != 0:
        return REQUIRED_R_PACKAGES
    raw = completed.stdout.strip()
    if not raw:
        return ()
    allowed = set(REQUIRED_R_PACKAGES)
    return tuple(pkg for pkg in (part.strip() for part in raw.split(",")) if pkg in allowed)


def _memory_bytes() -> int | None:
    if os.name == "nt":
        return _windows_memory()
    return _linux_memory()


def _windows_memory() -> int | None:
    windll = getattr(ctypes, "windll", None)
    kernel = getattr(windll, "kernel32", None) if windll is not None else None
    if kernel is None:
        return None

    class _Status(ctypes.Structure):
        _fields_ = (
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        )

    status = _Status()
    status.dwLength = ctypes.sizeof(status)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullAvailPhys)


def _linux_memory() -> int | None:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) * 1024
    return None
