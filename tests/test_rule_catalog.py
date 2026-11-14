"""Rule catalog ids stay unique so the coverage table cannot repeat a rule."""

from __future__ import annotations

from stagecraft_studio.rules.catalog import ROWS


def test_rule_ids_are_unique() -> None:
    ids = [row.rule_id for row in ROWS]
    assert len(ids) == len(set(ids))


def test_all_catalog_rules_are_implemented_and_tested() -> None:
    for row in ROWS:
        assert row.state == "已落实", row.rule_id
        assert row.location, row.rule_id
        assert row.test_id, row.rule_id
