# ContentEngine OpenCodeReview background

ContentEngine is MOTGU's durable content-production system. Review for correctness and invariant preservation, not stylistic preference.

Core invariants:
- backend is the workflow authority; frontend sends semantic intent only;
- human gates are explicit and exact: Angle, Outline, and final content;
- approvals bind exact artifact/version/hash and do not transfer to changed bytes;
- VI and EN writer lanes are independent and completed sibling work survives retry/failure;
- retries are bounded and ambiguous external outcomes reconcile before another side effect;
- durable Job/lease/checkpoint/resume behavior must survive restart;
- ContextManifest, evidence, settings and model-route lineage are immutable/auditable;
- hard quality failures block; warnings survive to human review;
- final editorial approval is not publication permission;
- operational DB, disposable test DB, code/CI proof, local runtime proof and publication are separate states;
- fail closed on ambiguity, stale state, inconsistent projections or unknown runtime health.

Review priorities:
1. data loss, approval bypass, duplicate side effects, stale binding, security;
2. broken recovery/idempotency/restart behavior;
3. workflow authority drift between backend and frontend;
4. missing negative-path tests for changed invariants;
5. maintainability issues only when they create concrete correctness risk.

Avoid low-value style findings.
