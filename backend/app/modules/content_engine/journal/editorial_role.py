"""Deterministic Pillar/Cluster editorial-role contracts for Journal production."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

JournalEditorialRole = Literal["pillar", "cluster"]
_VALID_ROLES = {"pillar", "cluster"}
_LEGACY_ROLE = "primary"


class EditorialRoleError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EditorialRoleContract:
    role: JournalEditorialRole
    objective: str
    breadth_rule: str
    depth_rule: str
    duplication_guard: str
    internal_link_rule: str

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "objective": self.objective,
            "breadth_rule": self.breadth_rule,
            "depth_rule": self.depth_rule,
            "duplication_guard": self.duplication_guard,
            "internal_link_rule": self.internal_link_rule,
        }


_CONTRACTS: dict[str, EditorialRoleContract] = {
    "pillar": EditorialRoleContract(
        role="pillar",
        objective=(
            "Synthesize the bounded main reader problem into one navigational answer "
            "that helps the reader understand the whole decision space."
        ),
        breadth_rule=(
            "Cover the committed main questions at useful overview depth. Do not expand "
            "indefinitely just because adjacent questions exist."
        ),
        depth_rule=(
            "Go deep enough to orient the reader and support a decision, then delegate "
            "narrow specialist detail to Cluster content when appropriate."
        ),
        duplication_guard=(
            "Do not reproduce full Cluster-level depth inside the Pillar merely to make "
            "the article longer."
        ),
        internal_link_rule=(
            "When narrower follow-up content exists or is planned, use internal-link "
            "intents to move the reader from the Pillar to the relevant Cluster."
        ),
    ),
    "cluster": EditorialRoleContract(
        role="cluster",
        objective=(
            "Resolve one bounded reader subproblem in greater depth than a broad Pillar "
            "overview."
        ),
        breadth_rule=(
            "Stay centered on the primary question and committed coverage. Do not widen "
            "into a general guide to the whole topic."
        ),
        depth_rule=(
            "Provide specific reasoning, evidence and practical detail for the bounded "
            "subproblem."
        ),
        duplication_guard=(
            "Do not restate the Pillar's broad synthesis as filler; add narrower depth "
            "or a distinct decision aid."
        ),
        internal_link_rule=(
            "When a parent Pillar relationship is known, link upward to it; use sideways "
            "Cluster links only when they directly help the reader continue."
        ),
    ),
}


def require_editorial_role(value: object) -> JournalEditorialRole:
    if not isinstance(value, str):
        raise EditorialRoleError("journal_editorial_role_invalid")
    normalized = value.strip().lower()
    if normalized not in _VALID_ROLES:
        raise EditorialRoleError("journal_editorial_role_invalid")
    return cast(JournalEditorialRole, normalized)


def editorial_role_contract(value: object) -> EditorialRoleContract:
    role = require_editorial_role(value)
    return _CONTRACTS[role]


def editorial_role_contract_or_none(value: object) -> EditorialRoleContract | None:
    """Return a contract for current roles while preserving legacy primary rows.

    Legacy rows are readable but never treated as if the Founder had selected a new
    Pillar/Cluster role.
    """

    if isinstance(value, str) and value.strip().lower() == _LEGACY_ROLE:
        return None
    return editorial_role_contract(value)


def is_current_editorial_role(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() in _VALID_ROLES


__all__ = [
    "EditorialRoleContract",
    "EditorialRoleError",
    "JournalEditorialRole",
    "editorial_role_contract",
    "editorial_role_contract_or_none",
    "is_current_editorial_role",
    "require_editorial_role",
]
