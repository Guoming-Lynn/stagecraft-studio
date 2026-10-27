"""Test that the gallery exposes the server-owned scientific status."""

from __future__ import annotations

import json
from pathlib import Path

from stagecraft_studio.db.gallery import get_stage_gallery
from stagecraft_studio.db.models import StageRun

from tests.test_gallery import _setup_stage


def test_gallery_uses_server_scientific_status_and_invalidates_it(tmp_path: Path) -> None:
    _, factory, run_id, _ = _setup_stage(tmp_path)
    with factory() as session:
        run = session.get(StageRun, run_id)
        assert run is not None
        run.evidence_json = json.dumps(
            {
                "verdict": {
                    "stopped": "FROZEN_PASS",
                    "fitted": True,
                    "model": "limma_voom",
                    "claims_limma": True,
                    "associated": True,
                    "holdout": "source_block_recorded",
                }
            }
        )
        session.commit()

        recorded = get_stage_gallery(session, run_id)["scientific_status"]
        assert recorded["scientific_status"] == "FROZEN_PASS"
        assert recorded["associated"] is True
        assert recorded["claims_limma"] is True
        assert recorded["holdout"] == "source_block_recorded"
        assert recorded["calibration_status"] == "NOT_ESTABLISHED_FOR_THIS_ANALYSIS"
        assert recorded["lodo_is_replication"] is False

        run.invalidated = True
        session.commit()
        invalidated = get_stage_gallery(session, run_id)["scientific_status"]
        assert invalidated["scientific_status"] == "INVALIDATED"
        assert invalidated["associated"] is False
        assert invalidated["claims_limma"] is False
        assert invalidated["read_only"] is True
