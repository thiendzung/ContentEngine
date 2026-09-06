from dataclasses import dataclass, replace
from itertools import chain

from app.modules.research.contracts import ResearchSignalKind, ResearchSpikeResult
from app.modules.research.keyword_plan.classify import (
    classify_question,
    query_quality,
)
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
    QueryQuality,
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
_RELEVANT_SUPPORT_TOPICS = {
    "choosing",
    "authenticity",
    "fit",
    "price",
    "logistics",
    "negotiation",
}
_OFF_SCOPE_TOPICS = {"painting_technique", "artist_process"}


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
        opportunities = [
            self._opportunity_for_cluster(hypothesis, cluster, request)
            for cluster in clusters
        ]

        pillar_clusters = self._pillar_clusters(
            clusters,
            request.pillar_question,
        )
        if request.pillar_question and len(pillar_clusters) >= 2:
            pillar = self._build_pillar_opportunity(
                hypothesis,
                pillar_clusters,
                request,
            )
            opportunities.insert(0, pillar)

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
        selected: ContentOpportunity | None = None
        updated: list[ContentOpportunity] = []
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
            if query_quality(signal.observed_text, seed_query=seed_query) in {
                QueryQuality.TRUNCATED,
                QueryQuality.MALFORMED,
            }:
                continue
            key = normalize_text(signal.observed_text)
            if key:
                grouped.setdefault(key, []).append(signal)

        records: list[QuestionRecord] = []
        for normalized_query, group in grouped.items():
            first = group[0]
            classification = classify_question(first.observed_text)
            records.append(
                QuestionRecord(
                    id=stable_id("q", locale, normalized_query),
                    query=first.observed_text,
                    locale=locale,
                    seed_query=seed_query,
                    signal_refs=tuple(item.id for item in group),
                    question_type=classification.question_type,
                    intent=classification.intent,
                    audience_stage=classification.audience_stage,
                    need_type=classification.need_type,
                    topic_key=classification.topic_key,
                    confidence=classification.confidence,
                    query_quality=classification.query_quality,
                )
            )
        return sorted(records, key=lambda item: (item.topic_key, item.query.casefold()))

    def _build_clusters(self, questions: list[QuestionRecord]) -> list[QuestionCluster]:
        grouped: dict[tuple[str, Intent], list[QuestionRecord]] = {}
        for question in questions:
            grouped.setdefault((question.topic_key, question.intent), []).append(question)

        clusters: list[QuestionCluster] = []
        for (topic_key, intent), group in grouped.items():
            primary = min(
                group,
                key=lambda item: (len(item.query), item.query.casefold()),
            )
            signal_refs = tuple(
                dict.fromkeys(chain.from_iterable(item.signal_refs for item in group))
            )
            clusters.append(
                QuestionCluster(
                    id=stable_id("cluster", topic_key, intent.value),
                    topic_key=topic_key,
                    intent=intent,
                    audience_stage=self._representative_stage(group),
                    need_type=self._representative_need_type(group),
                    primary_question=primary.query,
                    question_ids=tuple(item.id for item in group),
                    signal_refs=signal_refs,
                )
            )
        return sorted(clusters, key=lambda item: (item.topic_key, item.intent.value))

    def _pillar_clusters(
        self,
        clusters: list[QuestionCluster],
        pillar_question: str | None,
    ) -> list[QuestionCluster]:
        if not pillar_question:
            return []

        pillar_topic = classify_question(pillar_question).topic_key
        if pillar_topic not in _RELEVANT_SUPPORT_TOPICS:
            return []

        buyer_clusters = [
            cluster
            for cluster in clusters
            if cluster.topic_key in _RELEVANT_SUPPORT_TOPICS
            and cluster.topic_key not in _OFF_SCOPE_TOPICS
        ]
        has_direct_core_support = any(
            cluster.topic_key == pillar_topic for cluster in buyer_clusters
        )
        if not has_direct_core_support:
            return []
        return buyer_clusters

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
        present = {item.audience_stage for item in questions}
        return next(stage for stage in priority if stage in present)

    def _representative_need_type(self, questions: list[QuestionRecord]) -> NeedType:
        priority = (
            NeedType.PAIN,
            NeedType.OBJECTION,
            NeedType.QUESTION,
            NeedType.DESIRE,
            NeedType.CURIOSITY,
        )
        present = {item.need_type for item in questions}
        return next(need_type for need_type in priority if need_type in present)

    def _build_hypothesis(
        self,
        signals: list[Signal],
        questions: list[QuestionRecord],
        request: OpportunityMapRequest,
    ) -> NeedHypothesis:
        related_refs = {
            signal_ref
            for question in questions
            if question.topic_key in _RELEVANT_SUPPORT_TOPICS
            for signal_ref in question.signal_refs
        }
        independent = unique_signals(signals)
        support_refs = tuple(
            signal.id for signal in independent if signal.id in related_refs
        )
        known_ids = {signal.id for signal in signals}
        contradiction_refs = tuple(
            ref for ref in request.contradiction_signal_refs if ref in known_ids
        )

        alternatives = request.alternative_explanations or (
            (
                "Search behaviour may reflect general curiosity or comparison "
                "rather than purchase anxiety."
            ),
            (
                "Price, authenticity or shipping questions may be practical planning "
                "rather than fear of choosing wrong."
            ),
        )
        missing = list(request.missing_evidence)
        if not any(item.source_kind is SignalSourceKind.MOTGU for item in independent):
            missing.append("No reviewed MOTGU-direct signal yet for this need hypothesis.")
        if not contradiction_refs:
            missing.append(
                "No bounded contradiction signal has been reviewed yet; "
                "absence is not disproof."
            )
        if not any(item.source_kind is SignalSourceKind.MARKET for item in independent):
            missing.append(
                "No direct MARKET observation outside search-result signals "
                "has been reviewed yet."
            )

        return NeedHypothesis(
            id=stable_id(
                "need",
                request.project_id,
                request.locale,
                request.need_statement,
            ),
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

    def _opportunity_for_cluster(
        self,
        hypothesis: NeedHypothesis,
        cluster: QuestionCluster,
        request: OpportunityMapRequest,
    ) -> ContentOpportunity:
        matches = self._existing_matches(cluster, request.existing_content)
        has_material = bool(request.motgu_materials)
        off_scope = cluster.topic_key in _OFF_SCOPE_TOPICS
        decision = (
            ContentDecision.DO_NOT_WRITE
            if off_scope
            else self._decision(matches, has_material)
        )
        material_refs = (
            ()
            if off_scope
            else tuple(item.ref for item in request.motgu_materials)
        )
        material_gaps = () if off_scope else self._material_gaps(has_material)
        priority, reasons = self._priority(
            decision=decision,
            signal_count=len(cluster.signal_refs),
            has_material=has_material,
            question_count=len(cluster.question_ids),
        )
        suggested_type = self._suggested_content_type(
            cluster,
            request.motgu_materials,
        )
        role = JournalRole.CLUSTER
        return ContentOpportunity(
            id=stable_id("opp", hypothesis.id, cluster.id, decision.value),
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
            existing_content_refs=tuple(item.id for item in matches),
            what_is_actually_new=(
                "Off-scope art-making signal; retain for traceability but do not "
                "create buyer content."
                if off_scope
                else self._new_value(has_material)
            ),
            next_discovery_step=self._next_discovery_step(cluster.topic_key),
            decision=decision,
            priority=priority,
            reasons=reasons,
            suggested_content_type=suggested_type,
            suggested_role=(
                None
                if off_scope
                else role if suggested_type is SuggestedContentType.JOURNAL else None
            ),
        )

    def _build_pillar_opportunity(
        self,
        hypothesis: NeedHypothesis,
        clusters: list[QuestionCluster],
        request: OpportunityMapRequest,
    ) -> ContentOpportunity:
        signal_refs = tuple(
            dict.fromkeys(chain.from_iterable(item.signal_refs for item in clusters))
        )
        material_refs = tuple(item.ref for item in request.motgu_materials)
        has_material = bool(material_refs)
        priority, reasons = self._priority(
            decision=ContentDecision.CREATE,
            signal_count=len(signal_refs),
            has_material=has_material,
            question_count=sum(len(item.question_ids) for item in clusters),
        )
        promise = (
            "Give the reader one useful path through the main questions around: "
            f"{hypothesis.statement}"
        )
        return ContentOpportunity(
            id=stable_id(
                "opp",
                hypothesis.id,
                "pillar",
                request.pillar_question or "",
            ),
            need_hypothesis_id=hypothesis.id,
            locale=request.locale,
            reader=request.reader.strip(),
            situation=request.situation.strip(),
            need=hypothesis.statement,
            question=request.pillar_question or hypothesis.statement,
            intent=Intent.EVALUATE,
            promise=promise,
            topic_key="first_art_purchase",
            signal_refs=signal_refs,
            motgu_material_refs=material_refs,
            material_gaps=self._material_gaps(has_material),
            existing_content_refs=(),
            what_is_actually_new=self._pillar_new_value(has_material),
            next_discovery_step=request.business_path,
            decision=ContentDecision.CREATE,
            priority=priority,
            reasons=(*reasons, "covers_multiple_distinct_question_clusters"),
            suggested_content_type=SuggestedContentType.JOURNAL,
            suggested_role=JournalRole.PILLAR,
        )

    def _material_gaps(self, has_material: bool) -> tuple[str, ...]:
        if has_material:
            return ()
        return (
            "Add approved MOTGU-owned fact, observation, artwork or practical "
            "experience before drafting.",
        )

    def _new_value(self, has_material: bool) -> str:
        if has_material:
            return (
                "Use approved MOTGU-owned material to answer this question "
                "from a specific local point of view."
            )
        return (
            "Not established yet; keep this as a research candidate until "
            "MOTGU-owned material is attached."
        )

    def _pillar_new_value(self, has_material: bool) -> str:
        if has_material:
            return (
                "Connect several real questions through MOTGU-owned art-viewing "
                "and buying experience."
            )
        return "Broad synthesis is not differentiated without MOTGU-owned material."

    def _existing_matches(
        self,
        cluster: QuestionCluster,
        existing: tuple[ExistingContentRef, ...],
    ) -> list[ExistingContentRef]:
        return [
            item
            for item in existing
            if item.topic_key == cluster.topic_key and item.intent is cluster.intent
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
        reasons.append(
            "motgu_owned_material_available"
            if has_material
            else "motgu_owned_material_gap"
        )

        if decision is not ContentDecision.CREATE:
            reasons.append(f"existing_content_action:{decision.value}")
            return OpportunityPriority.NEXT, tuple(reasons)
        if signal_count >= 2 and has_material:
            return OpportunityPriority.NOW, tuple(reasons)
        if signal_count >= 1 and has_material:
            return OpportunityPriority.NEXT, tuple(reasons)
        return OpportunityPriority.LATER, tuple(reasons)

    def _suggested_content_type(
        self,
        cluster: QuestionCluster,
        materials: tuple[MotguMaterial, ...],
    ) -> SuggestedContentType:
        has_artwork = any(item.kind == "artwork" for item in materials)
        asks_specific_artwork = "this painting" in normalize_text(
            cluster.primary_question
        )
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
            item
            for item in opportunities
            if item.priority in {OpportunityPriority.NOW, OpportunityPriority.NEXT}
            and item.decision is not ContentDecision.DO_NOT_WRITE
        ]
        right_to_win = tuple(
            item.description
            for item in request.motgu_materials
            if item.description.strip()
        )
        if not usable or not right_to_win:
            return []

        signal_refs = tuple(
            dict.fromkeys(chain.from_iterable(item.signal_refs for item in usable))
        )
        question_pattern = " / ".join(item.question for item in usable[:3])
        content_gap = (
            "Search questions are fragmented; answer them with approved "
            "MOTGU-owned material instead of generic sales advice."
        )
        return [
            NicheCandidate(
                id=stable_id("niche", hypothesis.id, request.locale),
                audience=request.reader.strip(),
                need=hypothesis.statement,
                topic_key="first_art_purchase",
                question_pattern=question_pattern,
                content_gap=content_gap,
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
        if not any(item.scope.value == "motgu_site" for item in unique_signals(signals)):
            gaps.append("No MOTGU-site search/behaviour signal is included yet.")
        return list(dict.fromkeys(gaps))

    def _build_experiment_draft(
        self,
        result: OpportunityMapResult,
        opportunity: ContentOpportunity,
    ) -> ContentExperimentDraft:
        expected = (
            "The intended reader gets a clearer answer to the selected question "
            "and a natural next step to relevant MOTGU content or experience."
        )
        measurement_plan = (
            (
                "Review Search Console queries, impressions and clicks when "
                "enough exposure exists."
            ),
            (
                "Review useful transitions to related Artwork, Artist, Visit "
                "or Inquiry destinations."
            ),
            (
                "Record reviewed MOTGU-direct questions or inquiries that support "
                "or contradict the need hypothesis."
            ),
        )
        metric_definitions = (
            "search_visibility: query-family impressions and clicks",
            "useful_transition: qualified transition to a relevant next destination",
            "motgu_direct_signal: reviewed visitor or inquiry observation",
        )
        minimum_evidence = (
            "Do not conclude from one inquiry, one click or dwell time alone.",
            "Keep support and contradiction signals separate and traceable.",
            "If exposure is too small, result must remain INCONCLUSIVE.",
        )
        return ContentExperimentDraft(
            id=stable_id("exp", opportunity.id, str(result.need_hypothesis.version)),
            content_opportunity_id=opportunity.id,
            need_hypothesis_id=result.need_hypothesis.id,
            hypothesis_version=result.need_hypothesis.version,
            expected_behaviour=expected,
            measurement_plan=measurement_plan,
            metric_definitions=metric_definitions,
            minimum_evidence=minimum_evidence,
        )
