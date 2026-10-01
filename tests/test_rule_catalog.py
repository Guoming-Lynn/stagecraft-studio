"""Rule catalog ids stay unique so the coverage table cannot repeat a rule."""

from __future__ import annotations

from stagecraft_studio.rules.catalog import ROWS


def test_rule_ids_are_unique() -> None:
    ids = [row.rule_id for row in ROWS]
    assert len(ids) == len(set(ids))
