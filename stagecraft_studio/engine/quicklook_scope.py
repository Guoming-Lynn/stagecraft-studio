"""Decide how far a quicklook run may go.

Enrichment runs only when a local GMT file is present. The online enrichment
entry point is not selected here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CLUSTER_STOP = "phase03"
FULL_STOP = "phase04_sensitivity"


@dataclass(frozen=True)
class QuicklookScope:
    stop_after: str | None
    gmt_path: Path | None
    enrichment: str
    stopped_after: str


def plan_scope(gmt: Path | None) -> QuicklookScope:
    """Return the phase boundary for this GMT path."""
    if gmt is None:
        return QuicklookScope(
            stop_after=CLUSTER_STOP,
            gmt_path=None,
            enrichment="not_run_until_local_gmt",
            stopped_after=CLUSTER_STOP,
        )
    if not gmt.is_file():
        raise FileNotFoundError(gmt)
    return QuicklookScope(
        stop_after=None,
        gmt_path=gmt.resolve(),
        enrichment="local_gmt",
        stopped_after=FULL_STOP,
    )


def engine_argv(python: Path, script: Path, config_path: Path, scope: QuicklookScope) -> list[str]:
    command = [str(python), str(script), "--config", str(config_path)]
    if scope.stop_after is not None:
        command.extend(["--stop-after", scope.stop_after])
    return command
