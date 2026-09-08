# CE04 PR-E — Round 5 Evidence Review

Date: 2026-09-07
PR: #28

## Decision

Round 5 is `PIPELINE PASS / EVIDENCE QUALITY FAIL`.

Observed human-review result:

- useful supports: 3;
- suitable independent support domains: 1;
- only `www.irs.gov` qualifies as a strong independent factual source;
- `maddoxgallery.com` and `myartbroker.com` remain context-only;
- EvidenceSet v5 remains draft/unlocked;
- NeedHypothesis remains PROPOSED;
- no ContentRun or KnowledgeCandidate was created.

The quality Gate remains `>=2 useful supports from >=2 suitable independent domains`, so Round 5 must not be promoted or locked.

## Stop broad search

Do not run another broad search round. Search already found enough direction; the missing item is one second strong independent source.

A human-reviewed Smithsonian American Art Museum page is locked for a bounded supplement:

`https://americanart.si.edu/research/my-art/object-worth`

The page directly addresses artwork value and explains that fixed values are difficult to establish, while condition, buyer/seller interests and market trends affect the amount asked or offered. It also points readers to sale/auction prices and professional appraisers.

## Architecture decision

PR-E now includes a narrow `DirectSourceResearchRunner` and `backend/scripts/run_evidence_source_supplement.py`.

Boundary:

- no Serper/Tavily/Exa;
- exactly one human-reviewed public URL;
- Jina reads the source;
- the result is normalized into the existing `ProductionResearchResult` contract;
- the canonical EvidenceResearchWorkflow still performs claim extraction, exact excerpt validation, Evidence persistence and draft EvidenceSet versioning;
- no manual relation change;
- no lock;
- no fake ContentRun.

Only `.gov/.edu` remain automatic strong institutional candidates. Other domains require separate review.

## Next

Run exactly one Smithsonian direct-source supplement after the final branch CI is PASS.

If at least one direct O4 support survives human review, MG CONTENT ENGINE may combine exact reviewed IRS + Smithsonian Evidence IDs using the zero-provider curated EvidenceSet CLI.

Do not curate or lock until that supplement has been reviewed.
