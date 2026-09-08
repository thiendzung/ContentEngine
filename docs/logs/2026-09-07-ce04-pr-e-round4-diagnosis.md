# CE04 PR-E — Round 4 Diagnosis

Date: 2026-09-07
PR: #28
Branch: `ce04-evidence-research-evidence-set`

Status: `ROUND 4 QUALITY FAIL / ROOT CAUSE IDENTIFIED`

## Round 4 result

- EvidenceSet v4: `430966fb-b143-4179-a017-7875e54a4914` / draft / unlocked.
- Artifact SHA-256: `aaba83a7119ebb656c545186b146df5146082c143b9c847ae1c1523c01047949`.
- 3 readable SourceDocuments.
- 6 Evidence rows.
- persisted relations: `supports=1`, `context_only=5`.
- human gate: `1 useful support / 1 suitable support domain`.
- NeedHypothesis remains `PROPOSED`.
- ContentRun unchanged.

Do not lock v1/v2/v3/v4.

## Root cause 1 — Evidence subject is anchored to the wrong object

The persisted selected O4 planning object is:

`Question: Artsy prices`

The canonical NeedHypothesis is:

`A first-time art buyer wants to understand whether an original artwork price makes sense before deciding to buy.`

The Evidence extractor currently derives mandatory subject terms from `opportunity.question`.
That is a Discovery planning label, not the Evidence Research subject.

Impact:

- the literal word `prices` is treated as a subject anchor;
- a strong Museum Exchange appraisal sentence about `artwork + appraisal + comparable artworks` can be rejected because it does not contain the literal planning label/price wording;
- weaker price-bearing examples can survive even when they are less useful.

Decision:

Evidence subject anchoring must use the canonical NeedHypothesis statement explicitly. Opportunity question/need/promise and the research query remain relevance/scoring context only.

## Root cause 2 — domain-name authority is still too optimistic

Current source annotation still treats hostnames containing words such as `museum`, `archive`, `association`, `institute`, etc. as `institutional` candidates.

This remains unsafe for brand `.com` domains.

Reviewed examples:

- `museumexchange.com` describes itself as a digital art-donation/appraisal platform/company, not a public museum or standards authority.
- `artworkarchive.com` describes itself as a cloud art inventory/software platform, not an independent institutional authority.

Decision:

Automatic institutional classification must be conservative:

- `.gov` / `.edu` may remain strong institutional candidates;
- brand `.com` domains must NOT become `institutional` only because the hostname contains institutional-looking words;
- otherwise keep source authority/bias unknown unless another explicit trusted rule exists;
- human review may still judge an exact claim useful, but automatic authority metadata must not manufacture trust.

Historical Evidence rows remain immutable/auditable; do not silently rewrite old gate history.

## Root cause 3 — EvidenceSet needs explicit human curation

Current research workflow builds a draft EvidenceSet from all Evidence created in one run.
Human review, however, may identify the best Evidence across multiple bounded runs.

T04.22 requires EvidenceSet lock/version. The missing V1 capability is a minimal curation step:

`reviewed Evidence IDs -> draft EvidenceSet -> human review -> lock exact set`

This curation must:

- use existing persisted Evidence only;
- make zero provider calls;
- preserve Evidence rows and relations unchanged;
- validate same ContentCase/project;
- create/reuse a deterministic draft EvidenceSet from the exact selected IDs;
- print the exact set/version/status and `provider_calls=0`;
- remain draft until a separate lock command.

This is not a new review platform and does not start T04.24+.

## Candidate reviewed Evidence already available

Potentially useful human-reviewed rows include:

- Museum Exchange Round 3 direct artwork-appraisal support: `ecf4c902-74a3-4b58-9486-d00cf6ccc606`.
- Artwork Archive Round 4 fair-market-value support: `cabca0fa-e8d4-4f39-9fc0-e39d9bb314a9`.

These IDs must NOT be locked merely because they are listed here. After code repair, Agent Local must inspect their current persisted relation/source metadata and MG CONTENT ENGINE must make the final curated-set decision.

## Repair boundary

Implement only:

1. NeedHypothesis-based subject anchoring.
2. Conservative source annotation for institutional authority.
3. Minimal zero-provider EvidenceSet curation CLI/service.
4. Regression tests for the exact Round 4 failures.
5. AI_context sync.

No provider run, no EvidenceSet lock, no relation mutation, no KnowledgeCandidate, no T04.24+.