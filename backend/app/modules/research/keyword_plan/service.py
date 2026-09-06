from dataclasses import dataclass, replace
from itertools import chain

from app.modules.research.contracts import ResearchSignalKind, ResearchSpikeResult
from app.modules.research.keyword_plan.classify import classify_question
from app.modules.research.keyword_plan.contracts import (
    AudienceStage,
    ContentDecision,
    ContentExperimentDraft,
    ContentOpportunity,
    ExistingContentRef,
    HumanSelection,
    HypothesisStatus,
    Intent,
    JournalRole,
    MotguMaterial,
    NeedHypothesis,
    NeedType,
    NicheCandidate,
    OpportunityMapResult,
    OpportunityPriority,
    QuestionCluster,
    QuestionRecord,
    Signal,
    SignalSourceKind,
    SuggestedContentType,
)
from app.modules.research.keyword_plan.normalize import (
    mark_duplicate_signals,
    normalize_search_signals,
    normalize_text,
    stable_id,
    unique_signals,
)

_QUESTION_METHODS = {
    ResearchSignalKind.PEOPLE_ALSO_ASK.value,
    ResearchSignalKind.RELATED_SEARCH.value,
    ResearchSignalKind.AUTOCOMPLETE.value,
}
_STOPWORDS = {
    "a",
    "about",
    "and",
    "art",
    "buyer",
    "first",
    "of",
    "painting",
    "the",
    "time",
    "to",
}


@dataclass(slots=True, frozen=True)
class OpportunityMapRequest:
    project_id: str
    locale: str
    audience_scope: str
    situation: str
    reader: str
    need_statement: str
    need_type: NeedType
    seed_origin: str = "founder_proposed"
    artifact_ref: str | None = None
    motgu_materials: tuple[MotguMaterial, ...] = ()
    existing_content: tuple[ExistingContentRef, ...] = ()
    extra_signals: tuple[Signal, ...] = ()
    alternative_explanations: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    contradiction_signal_refs: tuple[str, ...] = ()
    pillar_question: str | None = None
    business_path: str = "Artwork / Artist / Visit / Inquiry"


class OpportunityMapService:
    def build(
        self,
        research: ResearchSpikeResult,
        request: OpportunityMapRequest,
    ) -> OpportunityMapResult:
        if not request.need_statement.strip():
            raise ValueError("need_statement_required")
        if not request.reader.strip():
            raise ValueError("reader_required")

        search_signals = normalize_search_signals(
            research,
            locale=request.locale,
            artifact_ref=request.artifact_ref,
        )
        signals = mark_duplicate_signals([*search_signals, *request.extra_signals])
        questions = self._build_questions(signals, research.seed, request.locale)
        clusters = self._build_clusters(questions)
        hypothesis = self._build_hypothesis(signals, questions, request)
        opportunities = self._build_opportunities(hypothesis, clusters, request)
        if request.pillar_question and len(clusters) >= 2:
            opportunities.insert(
                0,
                self._build_pillar_opportunity(
                    hypothesis,
                    clusters,
                    request,
                ),
            )
        niche_candidates = self._build_niche_candidates(
            hypothesis,
            opportunities,
            request,
        )
        research_gaps = self._research_gaps(hypothesis, signals, request)
        return OpportunityMapResult(
            project_id=request.project_id,
            locale=request.locale,
            seed=research.seed,
            version=1,
            need_hypothesis=hypothesis,
            signals=signals,
            questions=questions,
            clusters=clusters,
            opportunities=opportunities,
            niche_candidates=niche_candidates,
            research_gaps=research_gaps,
        )

    def select(
        self,
        result: OpportunityMapResult,
        *,
        opportunity_id: str,
        selected_by: str,
        reason: str,
    ) -> OpportunityMapResult:
        actor = selected_by.strip()
        selection_reason = reason.strip()
        if not actor:
            raise ValueError("selected_by_required")
        if not selection_reason:
            raise ValueError("selection_reason_required")

        selection = HumanSelection(
            opportunity_id=opportunity_id,
            selected_by=actor,
            reason=selection_reason,
        )
        updated: list[ContentOpportunity] = []
        selected: ContentOpportunity | None = None
        for opportunity in result.opportunities:
            if opportunity.id != opportunity_id:
                updated.append(opportunity)
                continue
            selected = replace(
                opportunity,
                selected_by=actor,
                selected_at=selection.selected_at,
                selection_reason=selection_reason,
            )
            updated.append(selected)
        if selected is None:
            raise ValueError("opportunity_not_found")
        if selected.decision is ContentDecision.DO_NOT_WRITE:
            raise ValueError("cannot_select_do_not_write")

        result.opportunities = updated
        result.human_selection = selection
        result.experiment_draft = self._build_experiment_draft(result, selected)
        return result

    def _build_questions(
        self,
        signals: list[Signal],
        seed_query: str,
        locale: str,
    ) -> list[QuestionRecord]:
        grouped: dict[str, list[Signal]] = {}
        for signal in unique_signals(signals):
            if signal.source_kind is not SignalSourceKind.SEARCH:
                continue
            if signal.provenance.method not in _QUESTION_METHODS:
                continue
            key = normalize_text(signal.observed_text)
            if not key:
                continue
            grouped.setdefault(key, []).append(signal)

        records: list[QuestionRecord] = []
        for normalized_query, grouped_signals in grouped.items():
            classification = classify_question(grouped_signals[0].observed_text)
            records.append(
                QuestionRecord(
                    id=stable_id("q", locale, normalized_query),
                    query=grouped_signals[0].observed_text,
                    locale=locale,
                    seed_query=seed_query,
                    signal_refs=tuple(signal.id for signal in grouped_signals),
                    question_type=classification.question_type,
                    intent=classification.intent,
                    audience_stage=classification.audience_stage,
                    need_type=classification.need_type,
                    topic_key=classification.topic_key,
                    confidence=classification.confidence,
                )
            )
        return sorted(records, key=lambda item: (item.topic_key, item.query.casefold()))

    def _build_clusters(self, questions: list[QuestionRecord]) -> list[QuestionCluster]:
        grouped: dict[tuple[str, Intent], list[QuestionRecord]] = {}
        for question in questions:
            grouped.setdefault((question.topic_key, question.intent), []).append(question)

        clusters: list[QuestionCluster] = []
        for (topic_key, intent), grouped_questions in grouped.items():
            stage = self._representative_stage(grouped_questions)
            need_type = self._representative_need_type(grouped_questions)
            primary = min(grouped_questions, key=lambda item: (len(item.query), item.query.casefold()))
            signal_refs = tuple(
                dict.fromkeys(chain.from_iterable(q.signal_refs for q in grouped_questions))
            )
            clusters.append(
                QuestionCluster(
                    id=stable_id("cluster", topic_key, intent.value),
                    topic_key=topic_key,
                    intent=intent,
                    audience_stage=stage,
                    need_type=need_type,
                    primary_question=primary.query,
                    question_ids=tuple(q.id for q in grouped_questions),
                    signal_refs=signal_refs,
                )
            )
        return sorted(clusters, key=lambda item: (item.topic_key, item.intent.value))

    def _representative_stage(self, questions: list[QuestionRecord]) -> AudienceStage:
        priority = (
            AudienceStage.FIRST_TIME_BUYER,
            AudienceStage.EVALUATING,
            AudienceStage.READY_TO_VISIT,
            AudienceStage.READY_TO_INQUIRE,
            AudienceStage.OWNER,
            AudienceStage.EXPLORING,
            AudienceStage.CURIOUS,
        )
        present = {question.audience_stage for question in questions}
        return next(stage for stage in priority if stage in present)

    def _representative_need_type(self, questions: list[QuestionRecord]) -> NeedType:
        priority = (
            NeedType.PAIN,
            NeedType.OBJECTION,
            NeedType.QUESTION,
            NeedType.DESIRE,
            NeedType.CURIOSITY,
        )
        present = {question.need_type for question in questions}
        return next(need_type for need_type in priority if need_type in present)

    def _build_hypothesis(
        self,
        signals: list[Signal],
        questions: list[QuestionRecord],
        request: OpportunityMapRequest,
    ) -> NeedHypothesis:
        related_question_ids = {
            signal_ref
            for question in questions
            if question.topic_key in {"choosing", "authenticity", "fit", "price"}
            for signal_ref in question.signal_refs
        }
        support_refs = tuple(
            signal.id
            for signal in unique_signals(signals)
            if signal.id in related_question_ids
        )
        contradiction_refs = tuple(
            signal_ref
            for signal_ref in request.contradiction_signal_refs
            if any(signal.id == signal_ref for signal in signals)
        )
        alternatives = request.alternative_explanations or (
            "Search behaviour may reflect general curiosity or comparison rather than purchase anxiety.",
            "A question about price, authenticity or shipping may be practical planning rather than fear of choosing wrong.",
        )
        missing = list(request.missing_evidence)
        if not any(signal.source_kind is SignalSourceKind.MOTGU for signal in unique_signals(signals)):
            missing.append("No reviewed MOTGU-direct signal yet for this need hypothesis.")
        if not contradiction_refs:
            missing.append("No bounded contradiction signal has been reviewed yet; absence is not disproof.")
        if not any(signal.source_kind is SignalSourceKind.MARKET for signal in unique_signals(signals)):
            missing.append("No direct MARKET observation outside search-result signals has been reviewed yet.")

        return NeedHypothesis(
            id=stable_id("need", request.project_id, request.locale, request.need_statement),
            statement=request.need_statement.strip(),
            audience_scope=request.audience_scope.strip(),
            situation=request.situation.strip(),
            need_type=request.need_type,
            origin=request.seed_origin,
            status=HypothesisStatus.PROPOSED,
            support_signal_refs=support_refs,
            contradict_signal_refs=contradiction_refs,
            alternative_explanations=tuple(dict.fromkeys(alternatives)),
            missing_evidence=tuple(dict.fromkeys(missing)),
        )

    def _build_opportunities(
        self,
        hypothesis: NeedHypothesis,
        clusters: list[QuestionCluster],
        request: OpportunityMapRequest,
    ) -> list[ContentOpportunity]:
        return [
            self._opportunity_for_cluster(hypothesis, cluster, request)
            for cluster in clusters
        ]

    def _opportunity_for_cluster(
        self,
        hypothesis: NeedHypothesis,
        cluster: QuestionCluster,
        request: OpportunityMapRequest,
    ) -> ContentOpportunity:
        matches = self._existing_matches(cluster, request.existing_content)
        decision = self._decision(matches, bool(request.motgu_materials))
        role = JournalRole.PILLAR if len(cluster.question_ids) >= 3 else JournalRole.CLUSTER
        material_refs = tuple(material.ref for material in request.motgu_materials)
        material_gaps = () if material_refs else (
            "Add at least one approved MOTGU-owned fact, observation, artwork or practical experience before drafting.",
        )
        priority, reasons = self._priority(
            decision=decision,
            signal_count=len(cluster.signal_refs),
            has_material=bool(material_refs),
            question_count=len(cluster.question_ids),
        )
        existing_refs = tuple(content.id for content in matches)
        new_value = (
            "Use approved MOTGU-owned material to answer this question from a specific local point of view."
            if material_refs
            else "Not established yet; the opportunity remains a research candidate until MOTGU-owned material is attached."
        )
        suggested_type = self._suggested_content_type(cluster, request.motgu_materials)
        return ContentOpportunity(
            id=stable_id(
                "opp",
                hypothesis.id,
                cluster.id,
                decision.value,
            ),
            need_hypothesis_id=hypothesis.id,
            locale=request.locale,
            reader=request.reader.strip(),
            situation=request.situation.strip(),
            need=hypothesis.statement,
            question=cluster.primary_question,
            intent=cluster.intent,
            promise=f"Help the reader answer: {cluster.primary_question}",
            topic_key=cluster.topic_key,
            signal_refs=cluster.signal_refs,
            motgu_material_refs=material_refs,
            material_gaps=material_gaps,
            existing_content_refs=existing_refs,
            what_is_actually_new=new_value,
            next_discovery_step=self._next_discovery_step(cluster.topic_key),
            decision=decision,
            priority=priority,
            reasons=reasons,
            suggested_content_type=suggested_type,
            suggested_role=role if suggested_type is SuggestedContentType.JOURNAL else None,
        )

    def _build_pillar_opportunity(
        self,
        hypothesis: NeedHypothesis,
        clusters: list[QuestionCluster],
        request: OpportunityMapRequest,
    ) -> ContentOpportunity:
        signal_refs = tuple(dict.fromkeys(chain.from_iterable(c.signal_refs for c in clusters)))
        material_refs = tuple(material.ref for material in request.motgu_materials)
        priority, reasons = self._priority(
            decision=ContentDecision.CREATE,
            signal_count=len(signal_refs),
            has_material=bool(material_refs),
            question_count=sum(len(cluster.question_ids) for cluster in clusters),
        )
        return ContentOpportunity(
            id=stable_id("opp", hypothesis.id, "pillar", request.pillar_question or ""),
            need_hypothesis_id=hypothesis.id,
            locale=request.locale,
            reader=request.reader.strip(),
            situation=request.situation.strip(),
            need=hypothesis.statement,
            question=request.pillar_question or hypothesis.statement,
            intent=Intent.EVALUATE,
            promise=f"Give the reader one useful path through the main questions around: {hypothesis.statement}",
            topic_key="first_art_purchase",
            signal_refs=signal_refs,
            motgu_material_refs=material_refs,
            material_gaps=() if material_refs else (
                "Add MOTGU-owned material before choosing this broad pillar direction.",
            ),
            existing_content_refs=(),
            what_is_actually_new=(
                "Connect several real questions through MOTGU-owned art-viewing and buying experience."
                if material_refs
                else "Broad synthesis is not yet differentiated without MOTGU-owned material."
            ),
            next_discovery_step=request.business_path,
            decision=ContentDecision.CREATE,
            priority=priority,
            reasons=(*reasons, "covers_multiple_distinct_question_clusters"),
            suggested_content_type=SuggestedContentType.JOURNAL,
            suggested_role=JournalRole.PILLAR,
        )

    def _existing_matches(
        self,
        cluster: QuestionCluster,
        existing: tuple[ExistingContentRef, ...],
    ) -> list[ExistingContentRef]:
        return [
            content
            for content in existing
            if content.topic_key == cluster.topic_key and content.intent is cluster.intent
        ]

    def _decision(
        self,
        matches: list[ExistingContentRef],
        has_material: bool,
    ) -> ContentDecision:
        if len(matches) > 1:
            return ContentDecision.MERGE
        if len(matches) == 1:
            match = matches[0]
            if match.stale:
                return ContentDecision.REFRESH
            if match.covers_answer and not has_material:
                return ContentDecision.LINK_ONLY
            return ContentDecision.UPDATE
        return ContentDecision.CREATE

    def _priority(
        self,
        *,
        decision: ContentDecision,
        signal_count: int,
        has_material: bool,
        question_count: int,
    ) -> tuple[OpportunityPriority, tuple[str, ...]]:
        if decision is ContentDecision.DO_NOT_WRITE:
            return OpportunityPriority.NO, ("decision_is_do_not_write",)
        reasons: list[str] = []
        if signal_count >= 2:
            reasons.append("repeated_search_question_signal")
        elif signal_count == 1:
            reasons.append("single_search_signal_only")
        else:
            reasons.append("no_search_signal_yet")
        if question_count >= 3:
            reasons.append("multiple_questions_share_one_answer_area")
        if has_material:
            reasons.append("motgu_owned_material_available")
        else:
            reasons.append("motgu_owned_material_gap")
        if decision is not ContentDecision.CREATE:
            reasons.append(f"existing_content_action:{decision.value}")
            return OpportunityPriority.NEXT, tuple(reasons)
        if signal_count >= 2 and has_material:
            return OpportunityPriority.NOW, tuple(reasons)
        if signal_count >= 1:
            return OpportunityPriority.NEXT if has_material else OpportunityPriority.LATER, tuple(reasons)
        return OpportunityPriority.LATER, tuple(reasons)

    def _suggested_content_type(
        self,
        cluster: QuestionCluster,
        materials: tuple[MotguMaterial, ...],
    ) -> SuggestedContentType:
        has_artwork = any(material.kind == "artwork" for material in materials)
        asks_specific_artwork = "this painting" in normalize_text(cluster.primary_question)
        if has_artwork and asks_specific_artwork:
            return SuggestedContentType.ARTWORK
        return SuggestedContentType.JOURNAL

    def _next_discovery_step(self, topic_key: str) -> str:
        if topic_key == "visit":
            return "Visit"
        if topic_key in {"authenticity", "fit", "choosing", "price"}:
            return "Relevant Artwork / Artist"
        if topic_key == "logistics":
            return "Practical buying/shipping guidance, then relevant Artwork"
        return "Related Journal / Artist / Artwork"

    def _build_niche_candidates(
        self,
        hypothesis: NeedHypothesis,
        opportunities: list[ContentOpportunity],
        request: OpportunityMapRequest,
    ) -> list[NicheCandidate]:
        usable = [
            opportunity
            for opportunity in opportunities
            if opportunity.priority in {OpportunityPriority.NOW, OpportunityPriority.NEXT}
            and opportunity.decision is not ContentDecision.DO_NOT_WRITE
        ]
        if not usable:
            return []
        right_to_win = tuple(
            material.description for material in request.motgu_materials if material.description.strip()
        )
        if not right_to_win:
            return []
        signal_refs = tuple(dict.fromkeys(chain.from_iterable(item.signal_refs for item in usable)))
        return [
            NicheCandidate(
                id=stable_id("niche", hypothesis.id, request.locale),
                audience=request.reader.strip(),
                need=hypothesis.statement,
                topic_key="first_art_purchase",
                question_pattern=" / ".join(item.question for item in usable[:3]),
                content_gap="Web/search questions are fragmented; the opportunity is to answer them with approved MOTGU-owned material instead of generic sales advice.",
                motgu_right_to_win=right_to_win,
                suggested_content_refs=tuple(item.id for item in usable[:5]),
                business_path=request.business_path,
                signal_refs=signal_refs,
            )
        ]

    def _research_gaps(
        self,
        hypothesis: NeedHypothesis,
        signals: list[Signal],
        request: OpportunityMapRequest,
    ) -> list[str]:
        gaps = list(hypothesis.missing_evidence)
        if not request.motgu_materials:
            gaps.append("MOTGU Right-to-Win material has not been attached yet.")
        unique = unique_signals(signals)
        if not any(signal.scope.value == "motgu_site" for signal in unique):
            gaps.append("No MOTGU-site search/behaviour signal is included yet.")
        return list(dict.fromkeys(gaps))

    def _build_experiment_draft(
        self,
        result: OpportunityMapResult,
        opportunity: ContentOpportunity,
    ) -> ContentExperimentDraft:
        return ContentExperimentDraft(
            id=stable_id("exp", opportunity.id, str(result.need_hypothesis.version)),
            content_opportunity_id=opportunity.id,
            need_hypothesis_id=result.need_hypothesis.id,
            hypothesis_version=result.need_hypothesis.version,
            expected_behaviour=(
                "The intended reader gets a clearer answer to the selected question and has a natural next step to relevant MOTGU content or experience."
            ),
            measurement_plan=(
                "Review Search Console queries/impressions/clicks for the published content when enough exposure exists.",
                "Review useful transitions to related Artwork, Artist, Visit or Inquiry destinations.",
                "Record reviewed MOTGU-direct questions/inquiries that support or contradict the need hypothesis.",
            ),
            metric_definitions=(
                "search_visibility: impressions/clicks for query families mapped to this opportunity",
                "useful_transition: qualified transition to a relevant next destination",
                "motgu_direct_signal: reviewed visitor/inquiry observation linked to this hypothesis",
            ),
            minimum_evidence=(
                "Do not conclude from one inquiry, one click or dwell time alone.",
                "Keep support and contradiction signals separate and traceable.",
                "If exposure is too small, result must remain INCONCLUSIVE.",
            ),
        )
