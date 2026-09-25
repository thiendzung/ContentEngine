from __future__ import annotations

import pytest

from app.modules.content_engine.journal.editorial_role import (
    EditorialRoleError,
    editorial_role_contract,
    editorial_role_contract_or_none,
    require_editorial_role,
)


def test_pillar_and_cluster_contracts_are_distinct_editorial_jobs() -> None:
    pillar = editorial_role_contract("pillar")
    cluster = editorial_role_contract("cluster")

    assert pillar.role == "pillar"
    assert cluster.role == "cluster"
    assert pillar.to_dict() != cluster.to_dict()
    assert "whole decision space" in pillar.objective
    assert "one bounded reader subproblem" in cluster.objective
    assert "Cluster-level depth" in pillar.duplication_guard
    assert "Pillar's broad synthesis" in cluster.duplication_guard


def test_role_normalization_accepts_current_roles_only() -> None:
    assert require_editorial_role(" PILLAR ") == "pillar"
    assert require_editorial_role("cluster") == "cluster"

    for value in ("primary", "article", "", None):
        with pytest.raises(EditorialRoleError, match="journal_editorial_role_invalid"):
            require_editorial_role(value)


def test_legacy_primary_or_missing_role_remains_readable_without_invented_contract() -> None:
    assert editorial_role_contract_or_none("primary") is None
    assert editorial_role_contract_or_none(None) is None
