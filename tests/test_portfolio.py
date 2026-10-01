"""Portfolio clicks stay on files inside the run."""

from __future__ import annotations

import json
from pathlib import Path

from stagecraft_studio.api.portfolio import read_portfolio


def test_portfolio_tiles_stay_inside_the_run(tmp_path: Path) -> None:
    folder = tmp_path / "06_portfolio"
    figure = tmp_path / "04_figures" / "01_qc"
    folder.mkdir()
    figure.mkdir(parents=True)
    (folder / "IFITM3_all_figures_dense_v2.png").write_bytes(b"png")
    (figure / "cell_counts_clean.png").write_bytes(b"png")
    (figure / "cell_counts_clean.csv").write_text("a\n", encoding="utf-8")
    payload = {
        "canvas_width_px": 100,
        "canvas_height_px": 80,
        "sections": [
            {
                "figures": [
                    {
                        "relative_source": "04_figures/01_qc/cell_counts_clean.png",
                        "table": "04_figures/01_qc/cell_counts_clean.csv",
                        "x": 1,
                        "y": 2,
                        "width": 10,
                        "height": 8,
                    },
                    {
                        "relative_source": "../secret.png",
                        "table": "",
                        "x": 0,
                        "y": 0,
                        "width": 1,
                        "height": 1,
                    },
                ]
            }
        ],
    }
    manifest = folder / "IFITM3_all_figures_dense_v2.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    view = read_portfolio(tmp_path)
    assert view is not None
    assert view.image == "06_portfolio/IFITM3_all_figures_dense_v2.png"
    assert [(tile.rel, tile.table) for tile in view.tiles] == [
        ("04_figures/01_qc/cell_counts_clean.png", "04_figures/01_qc/cell_counts_clean.csv")
    ]
