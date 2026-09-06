from pathlib import Path

from app.modules.research.artifact import research_spike_json
from app.modules.research.contracts import (
    ResearchSignalKind,
    ResearchSpikeResult,
    SearchSignal,
)
from app.modules.research.keyword_plan.artifact import (
    load_research_spike_for_opportunity_map,
    opportunity_map_markdown,
)
from app.modules.research.keyword_plan.classify import classify_question
from app.modules.research.keyword_plan.contracts import (
    Confidence,
    ContentDecision,
    ExistingContentRef,
    HypothesisStatus,
    Intent,
    JournalRole,
    MotguMaterial,
    NeedType,
    OpportunityPriority,
    QueryQuality,
)
from app.modules.research.keyword_plan.normalize import normalize_text
from app.modules.research.keyword_plan.service import (
    OpportunityMapRequest,
    OpportunityMapService,
)

SEED = "First-time art buyer worries about choosing the wrong painting."


def _signal(
    text: str,
    *,
    kind: ResearchSignalKind = ResearchSignalKind.PEOPLE_ALSO_ASK,
    provider: str = "serper",
) -> SearchSignal:
    return SearchSignal(
        provider=provider,
        query=SEED,
        kind=kind,
        text=text,
    )


def _research(*signals: SearchSignal) -> ResearchSpikeResult:
    return ResearchSpikeResult(seed=SEED, signals=list(signals))


def _request(
    *,
    materials: tuple[MotguMaterial, ...] = (),
    existing: tuple[ExistingContentRef, ...] = (),
    pillar_question: str | None = None,
) -> OpportunityMapRequest:
    return OpportunityMapRequest(
        project_id="motgu",
        locale="en",
        audience_scope="international first-time art buyer",
        situation="interested in original art but uncertain how to choose",
        reader="international first-time art buyer",
        need_statement=SEED,
        need_type=NeedType.PAIN,
        motgu_materials=materials,
        existing_content=existing,
        pillar_question=pillar_question,
    )


def test_search_duplicates_are_retained_but_not_counted_as_independent() -> None:
    research = _research(
        _signal("How do I know what art I like?"),
        _signal(
            "How do I know what art I like?",
            kind=ResearchSignalKind.AUTOCOMPLETE,
        ),
        _signal("How much should I spend on my first painting?"),
    )

    result = OpportunityMapService().build(research, _request())

    assert result.need_hypothesis.status is HypothesisStatus.PROPOSED
    assert len(result.signals) == 3
    assert sum(item.duplicate_of is not None for item in result.signals) == 1
    assert len(result.questions) == 2
    assert all(
        item.priority is OpportunityPriority.LATER
        for item in result.opportunities
    )


def test_opportunity_map_builds_pillar_clusters_and_niche_from_owned_material() -> None:
    material = MotguMaterial(
        ref="motgu:real-artwork-viewing",
        kind="first_party_experience",
        description=(
            "MOTGU can show real original artworks and explain practical "
            "viewing choices in Hanoi."
        ),
    )
    research = _research(
        _signal("How do I know what art I like?"),
        _signal("How can I tell if a painting is original?"),
        _signal("How much should I spend on my first painting?"),
        _signal("How do I bring a painting home from Vietnam?"),
    )
    pillar_question = (
        "How can a first-time buyer choose an original painting with confidence?"
    )

    result = OpportunityMapService().build(
        research,
        _request(
            materials=(material,),
            pillar_question=pillar_question,
        ),
    )

    assert len(result.clusters) >= 3
    assert result.opportunities[0].suggested_role is JournalRole.PILLAR
    assert result.opportunities[0].priority is OpportunityPriority.NOW
    assert result.niche_candidates
    assert result.niche_candidates[0].motgu_right_to_win == (material.description,)
    assert "No reviewed MOTGU-direct signal yet" in " ".join(result.research_gaps)


def test_existing_content_changes_create_decision_to_refresh_or_link_only() -> None:
    research = _research(_signal("How can I tell if a painting is original?"))
    stale = ExistingContentRef(
        id="journal-authenticity",
        primary_question="How do I know if a painting is original?",
        intent=Intent.TRUST,
        topic_key="authenticity",
        stale=True,
    )
    result = OpportunityMapService().build(research, _request(existing=(stale,)))
    authenticity = next(
        item for item in result.opportunities if item.topic_key == "authenticity"
    )
    assert authenticity.decision is ContentDecision.REFRESH

    covered = ExistingContentRef(
        id="journal-authenticity-current",
        primary_question="How do I know if a painting is original?",
        intent=Intent.TRUST,
        topic_key="authenticity",
        covers_answer=True,
    )
    result = OpportunityMapService().build(research, _request(existing=(covered,)))
    authenticity = next(
        item for item in result.opportunities if item.topic_key == "authenticity"
    )
    assert authenticity.decision is ContentDecision.LINK_ONLY


def test_human_selection_creates_experiment_without_promoting_hypothesis() -> None:
    material = MotguMaterial(
        ref="motgu:viewing",
        kind="first_party_experience",
        description="Reviewed MOTGU viewing guidance.",
    )
    research = _research(
        _signal("How do I know what art I like?"),
        _signal("How much should I spend on my first painting?"),
    )
    service = OpportunityMapService()
    result = service.build(research, _request(materials=(material,)))
    selected_id = result.opportunities[0].id

    selected = service.select(
        result,
        opportunity_id=selected_id,
        selected_by="founder",
        reason="Best fit for the first Golden Journal experiment.",
    )

    assert selected.human_selection is not None
    assert selected.human_selection.opportunity_id == selected_id
    assert selected.need_hypothesis.status is HypothesisStatus.PROPOSED
    assert selected.experiment_draft is not None
    assert selected.experiment_draft.need_hypothesis_id == selected.need_hypothesis.id


def test_research_artifact_loader_reuses_pr_b_signals(tmp_path: Path) -> None:
    research = _research(
        _signal("How do I know what art I like?"),
        _signal("How much should I spend on my first painting?"),
    )
    path = tmp_path / "research.json"
    path.write_text(research_spike_json(research), encoding="utf-8")

    loaded = load_research_spike_for_opportunity_map(path)
    result = OpportunityMapService().build(loaded, _request())
    markdown = opportunity_map_markdown(result)

    assert loaded.seed == SEED
    assert len(loaded.signals) == 2
    assert "# Opportunity Map Mini" in markdown
    assert "Status: PROPOSED" in markdown
    assert "## Opportunities" in markdown


def test_normalize_text_preserves_vietnamese_letters() -> None:
    assert normalize_text("Tranh Việt — Hà Nội") == "tranh việt hà nội"


def test_truncated_query_is_kept_as_signal_but_excluded_from_questions_and_pillar() -> None:
    truncated = "First time art buyer worries about choosing the wrong painting qui"
    research = _research(
        _signal(truncated),
        _signal("How do I know what art I like?"),
        _signal("How much should I spend on my first painting?"),
    )

    result = OpportunityMapService().build(
        research,
        _request(
            pillar_question=(
                "How can a first-time buyer choose an original painting with confidence?"
            )
        ),
    )

    assert len(result.signals) == 3
    assert truncated not in {item.query for item in result.questions}
    assert result.opportunities[0].suggested_role is JournalRole.PILLAR
    assert truncated not in result.opportunities[0].question
    assert all(truncated not in item.question for item in result.opportunities)


def test_painting_technique_is_off_scope_and_do_not_write() -> None:
    classification = classify_question("What is the 1/3 rule in painting?")
    assert classification.topic_key == "painting_technique"
    assert classification.query_quality is QueryQuality.OFF_SCOPE

    result = OpportunityMapService().build(
        _research(_signal("What is the 1/3 rule in painting?")),
        _request(),
    )
    opportunity = result.opportunities[0]
    assert opportunity.decision is ContentDecision.DO_NOT_WRITE
    assert opportunity.priority is OpportunityPriority.NO
    assert opportunity.suggested_role is None


def test_artist_process_is_off_scope_and_do_not_write() -> None:
    result = OpportunityMapService().build(
        _research(_signal("What do painters do when they make a mistake?")),
        _request(),
    )

    question = result.questions[0]
    assert question.topic_key == "artist_process"
    assert question.query_quality is QueryQuality.OFF_SCOPE
    assert result.opportunities[0].decision is ContentDecision.DO_NOT_WRITE
    assert result.opportunities[0].priority is OpportunityPriority.NO


def test_negotiation_is_a_purchase_objection() -> None:
    classification = classify_question("Can you negotiate with art galleries")

    assert classification.topic_key == "negotiation"
    assert classification.need_type is NeedType.OBJECTION
    assert classification.intent is Intent.EVALUATE
    assert classification.confidence is not Confidence.LOW


def test_pillar_only_counts_buyer_relevant_clusters() -> None:
    research = _research(
        _signal("How do I know what art I like?"),
        _signal("How much should I spend on my first painting?"),
        _signal("What is the 1/3 rule in painting?"),
        _signal("What do painters do when they make a mistake?"),
    )

    result = OpportunityMapService().build(
        research,
        _request(
            pillar_question=(
                "How can a first-time buyer choose an original painting with confidence?"
            )
        ),
    )

    pillar = result.opportunities[0]
    assert pillar.suggested_role is JournalRole.PILLAR
    assert len(pillar.signal_refs) == 2
    assert all(
        item.topic_key not in {"painting_technique", "artist_process"}
        for item in result.opportunities[:1]
    )
