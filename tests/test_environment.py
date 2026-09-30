"""Environment rows come from the server, including the fail text."""

from __future__ import annotations

from stagecraft_studio.api.environment import environment_report


def test_environment_report_separates_pass_and_fail() -> None:
    report = environment_report(
        python_version="3.11.15",
        r_version=None,
        engine_version="0.1.0",
        engine_name="scrna-target-engine",
        memory_bytes=1024,
        disk_free_bytes=20 * 1024**3,
    )
    by_name = {item.name: item for item in report.checks}
    assert by_name["python"].label == "通过"
    assert by_name["engine"].detail == "scrna-target-engine 0.1.0"
    assert by_name["r"].label == "不通过"
    assert "Rscript" in by_name["r"].fix
    assert by_name["memory"].label == "不通过"
    assert "8 GB" in by_name["memory"].fix
    assert by_name["disk"].label == "通过"
