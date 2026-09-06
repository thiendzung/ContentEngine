from datetime import datetime, timezone
from uuid import uuid4

from app.modules.content_engine.models import ContentOpportunity, Signal
from app.modules.content_engine.persistence import (
    opportunity_has_required_existing_target,
    signal_has_traceable_locator,
)


def test_signal_requires_traceable_locator_by_service_contract() -> None:
    signal = Signal(
        project_id=uuid4(),
        source_kind="SEARCH",
        scope="market_web",
        observed_text="Question",
        locale="en",
        context="test",
        captured_at=datetime.now(timezone.utc),
        fingerprint=uuid4().hex,
        provenance_json={"provider": "fixture", "method": "test"},
    )
    assert signal_has_traceable_locator(signal) is False

    signal.provenance_json["locator"] = "result[0]"
    assert signal_has_traceable_locator(signal) is True


def test_update_like_opportunity_requires_existing_target() -> None:
    opportunity = ContentOpportunity(
        project_id=uuid4(),
        need_hypothesis_id=uuid4(),
        locale="en",
        reader="reader",
        situation="situation",
        need="need",
        question="question",
        intent="evaluate",
        promise="promise",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="new",
        next_discovery_step="next",
        decision="UPDATE",
        priority="NEXT",
        reasons_json=[],
        suggested_content_type="journal",
    )
    assert opportunity_has_required_existing_target(opportunity) is False

    opportunity.existing_content_refs_json = ["journal-existing"]
    assert opportunity_has_required_existing_target(opportunity) is True
