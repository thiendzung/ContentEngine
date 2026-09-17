# ContentEngine - fast-track completion plan

Date: 2026-09-17
Status: DELIVERY PLAN IN PR #106; not a merge, deployment, publication or new real-model grant.
Authority: preserve Spec 21 and the existing F4 contract; preserve F0-F8 / AO / O identifiers.
Detailed contracts: `../AGENT-OPERATED-DELIVERY-TASKS.md` and `../AGENT-OPERATED-ACCEPTANCE.md`.

## Outcome

Deliver one useful Journal production path: objectives -> research -> Angle review -> Outline review -> independent VI/EN drafts -> quality -> final review -> exact approved ContentVersions / COMPLETE. No publication.

Target experience: agents perform permitted production work; Founder makes the three content decisions. Engineering remains MG code/review/plan -> Founder copies task -> Agent Local verifies -> MG reviews evidence -> Founder merges/releases.

Two milestones must not be confused:
- Backend normal path: accepted F4 and F5.1; full F5 includes revision/rejection in F5.2.
- Controlled agent-operated production: F5.2, AO-1, AO-2, minimum F6 UI and O1 also accepted. F7 establishes useful repeatability, not universal platform readiness.

## Dated baseline and evidence limits

GitHub reads: #105 is open/Draft at `42980c6ec1591284051e0b956f9511be3722a068`; main base remains merged F3 `5eef4e72cb15bc6ea30488a15f18a5de091053d6`. CI #1057 last verified successful for that candidate. #106 is documentation and remains subject to Founder merge.

Founder-relayed local report: F4-A5R-B0.2 reached Outline gate for case `d5347dcb-802e-45b4-8e99-0ccfe6bec5dc`, run `358f96f5-8ac5-4c8a-a5d5-ac4559b30a44`, TEST DB `contentengine_f4_b0_r2_test` on `127.0.0.1:55448`. Outline `77c121a2-9509-4970-8948-7829bf48439d`, v1, hash `95444ea13cfd15adabfdfd90913ff7e8eb0b5f865c9bcc87f5fec6730364bd5f`. Gate state `2b77d41ebd0cd80992f492779991407515bd1ef380c507d527737849ea2e3dfe`. Approval decision recorded in #105 comment 5710896953; local persistence is NOT yet evidenced.

A5 previously reached a correctly settled hard block in both locales; its history is retained. Review v3 addresses the missing closing-support contract. The current successor has not yet demonstrated the real quality success path. No report of local safety is an independent MG machine inspection.

## Delivery rules that remove avoidable delays

- Freeze one acceptance candidate. Keep this planning update on #106, not #105. Do not invalidate F4 acceptance with unrelated documentation/polish commits.
- One implementation owner, one scoped local verifier. While Local tests a frozen candidate, MG prepares the next contract/read-model/test design. No competing F4 code stream, shared-worktree writes or second worker on the acceptance DB.
- One task packet and one evidence packet per meaningful gate. Include complete artifact/version/hash, canonical state, exact content, findings and side effects the first time; no routine ANGLEVIEW/ANGLEBIND follow-up.
- Fakes and captured regression inputs first; bounded real calls only after review and CI. A real-model run is not a substitute for implementation tests.
- Save a private, consistent pre-quality snapshot after Writers. Any later restore must be explicitly scoped to a NEW isolated TEST destination; never rewind or erase the failed original DB. Verify restored lineage before use. This avoids repeating research/Angle/Outline solely because a downstream code fix is tested.
- An unchanged exact artifact can reuse its valid decision only through the established snapshot/lineage contract. New artifact bytes/identity need a new human decision. No copied/fabricated approvals.
- Classify failures: code/contract defect -> deterministic reproduction and minimal patch; insufficient content evidence -> content hold; uncertain external call -> reconcile first; polish -> backlog. No automatic replacement case after every failure.
- Current F4 has no authorized post-audit repair loop. F5.2 supplies versioned revision later. Immutable history forbids overwriting it, not a future explicit new revision with new checks.
- A new success fixture without ISA is NOT proof that the old closing defect is repaired. Retain separate regression coverage for a factual closing lacking refs and for the Review-v3 support policy. Do not weaken Audit or claim stronger semantic proof than tests provide.
- Finish a package when its published exit criteria pass. Do not expand it to improve an already acceptable article or build a framework.
- Planning is not blanket runtime authorization. A5's unused 4/8 calls do not transfer to a new head/case. New A5R quality execution needs its own bounded permission. Actual invocations, including failed/uncertain ones, count; missing costs stay unknown.

## Ordered work packages

### F4 - close the active quality slice (#105)

Owner: MG code/review; Agent Local runtime proof; Founder decisions/merge.
Next local packet: `2026-09-17-f4-a5r-b0-3-writer-task.md`.

- [ ] Persist the already-recorded exact Outline decision through `submit_operator_decision()` and verify its OperatorCommand receipt.
- [ ] One semantic Continue -> two independent Writers, maximum four total Writer invocations; no sibling regeneration.
- [ ] Return complete VI/EN draft content, exact refs, unresolved claims and source-scope findings; stop at `writers_to_quality`.
- [ ] Preserve a private pre-quality snapshot and its checksum/lineage manifest; no operational DB access.
- [ ] Verify regression coverage for the prior closing failure; changes require a newly frozen candidate and CI, not ad-hoc runtime repair.
- [ ] Separately authorize A5R quality, maximum eight real Review/Audit invocations, deterministic Source-copy, no research or new editorial approval.
- [ ] Both locales reach `AWAITING_APPROVAL / final_review`; final bytes/hash equal the qualified revised drafts, warnings retained, parent command settled, no queued/leased quality jobs.
- [ ] Final approvals, ContentVersions and publication delta remain zero. Preserve Angle/Outline approvals already given.
- [ ] MG reconciles code/CI/local evidence and updates #105 disposition; Founder merges. Do not start F5 execution before this exit.

### F5.1 - exact final decisions, versions and completion

Prerequisite: accepted/merged F4. Owner: MG; local proof: Agent Local.

- [ ] Bind human final decisions to every displayed locale artifact, warning and quality result using exact snapshots.
- [ ] Persist canonical ContentItem/ContentVersion and a recoverable receipt; COMPLETE requires every required locale, not merely row count.
- [ ] Prove double-submit/lost-response replay, stale/wrong-case rejection and interruption recovery without duplicate versions.
- [ ] Export exact approved content without a model call; status is Approved / Not published.
- [ ] Expose current state, review snapshot, permitted actions, warnings and version links for UI; no unsupported revision button.
- [ ] Preserve M1 and prior decisions. Local acceptance performs no research, generation or publication.

Exit: a qualified bilingual case can become approved ContentVersions / COMPLETE. Full revision handling still pending F5.2. Tests: H01-H03, C01-C03 in the existing matrix.

### AO-1 - real operator/reviewer separation

Prerequisite: F5.1 contracts; use completed AO-D0, do not repeat the survey. Owner: MG; restricted-profile local proof: Agent Local.

- [ ] Derive actor and role on the server: operator, reviewer, maintenance; reject client role/actor spoofing and alternate/legacy approval paths.
- [ ] One durable OperatingGrant binds cases, actions, immutable settings, expiry/revocation and explicit budgets; reserve/check budget before dispatch.
- [ ] Restricted operator cannot read reviewer credentials/.env, write deployed code, access DB/Docker/SSH/GitHub write capabilities, or bypass through old APIs.
- [ ] Test actual denials with the restricted profile, not the unrestricted engineering session. A proxy or sandbox claim alone is not proof.
- [ ] Keep a simple local identity mechanism, not a SaaS account/team platform. Any required migration is reviewed separately from F4.

Exit: agent can operate allowed transitions but cannot approve content or alter deployment. Tests: S01-S06, B01-B03 as applicable. No production activation yet.

### F5.2 - request changes and rejection without full restarts

Prerequisites: F5.1 + AO-1. Owner: MG; Founder supplies real content decisions.

- [ ] Implement exact gate/locale/artifact-bound Request changes(reason) and Reject for Angle, Outline and final content.
- [ ] A revision creates new immutable bytes; invalidate only dependent work. Locale-only final revision preserves valid sibling content.
- [ ] Recheck changed bytes and return to the correct human gate; old approvals/checks cannot certify the new version.
- [ ] Reject is terminal. Separate editorial cycle limits from technical retries; both survive restart.
- [ ] Hard-audit repair remains disabled unless separately enabled by an explicit bounded policy; no hidden post-audit rewriting.
- [ ] Prove one authorized revision path plus fake tests for all gates, stale work and limit exhaustion.

Exit: ordinary feedback does not require SQL, a new case, or restarting all approved work. Tests: H03-H05, Q03, B02, C02.

### AO-2 - automatic permitted continuation

Prerequisites: AO-1 + F5.2. Owner: MG; persistent local proof: Agent Local.

- [ ] Thin deterministic supervisor reads backend state; no LLM polling, new workflow engine or model-native daemon dependency.
- [ ] Persist wake-up/command identity; human approval resumes permitted work without a second Continue click or copied stage prompt.
- [ ] One fenced case-controller lease, distinct from Job leases; duplicate wake-ups/restarts cannot duplicate confirmed work.
- [ ] Missed wake-ups reconcile from durable state; uncertain external effects hold rather than silently repeat.
- [ ] WAIT_HUMAN waits quietly; pause/revoke blocks new dispatch and exposes truthful in-flight status.
- [ ] Start with one active Journal and one proven restricted adapter using the existing approved Codex route. Antigravity remains optional.

Exit: operator continues after real human decisions and returns to the next gate with no normal technical relay. Tests: E01-E05, R01-R05, B01-B03, S05.

### F6.2 + minimum F6.1 - usable reviewer workspace

Define its read-model while implementing backend slices; integrate after protected decisions/supervisor are ready. Owner: MG design/code; Agent Local browser tests; Founder usability review.

- [ ] Header: MOTGU ContentEngine, actual environment and readiness. Menu: Review / Production / System. Compact footer: version and refresh/health age; unknown is visible.
- [ ] Body: simple pending-review list and `/operator/journal/[caseId]`; no complex dense Board prerequisite.
- [ ] Display full Angle choices, Outline and final VI/EN with relevant sources/warnings; technical IDs in expandable details.
- [ ] Approve / Request changes / Reject use exact displayed snapshot and reviewer identity. Never auto-approve unseen newer content.
- [ ] Test double-click, stale tab, refresh, lost response and unsent comments; retain input after network errors.
- [ ] Usable loading/empty/error/offline/blocked states, narrow screens, keyboard/focus/contrast/non-color-only status before pilot.
- [ ] Demonstrate one complete browser review journey including a requested revision; no routine terminal or Continue instruction to Founder.

Exit: complete minimum header/menu/body/footer and real content-review flow. Tests: U01-U04 plus applicable H cases. Advanced Board, filters and animation wait.

### O1 - safe controlled local release

Prerequisites: above code and acceptance. Owner: Agent Local under a separate exact release task; MG review; Founder release authority.

- [ ] Re-identify actual operational schema, data and API/UI/worker/supervisor ownership. Historical 0027/0034 logs are not live schema proof.
- [ ] Fresh backup plus restore proof in a separate destination; verify representative artifacts, approvals, checkpoints and versions.
- [ ] Pin all released components to the intended release, separate TEST from operational data, preserve dirty work and retained cases.
- [ ] Perform only an explicitly approved source->target migration; no volume/role/password repair or destructive cleanup.
- [ ] Prove restricted credentials, loopback bindings, restart/reconciliation and supported rollback/recovery.
- [ ] Activate only a separately approved bounded case/batch grant. Release permission is not publication or unlimited model permission.

Exit: READY FOR CONTROLLED PRODUCTION. O2 routing changes are optional, not first-release scope by default.

### F7 - two useful real bilingual cases

Prerequisites: O1 + explicit objectives/content-call grants. Owner: restricted operator; Founder reviews; MG/Local collect engineering evidence.

- [ ] Two distinct useful MOTGU topics beyond historical M1; current pricing acceptance fixture is not a production pilot case.
- [ ] Complete all three human gates and at least one requested revision across the pilot, with exact approved versions and no publication.
- [ ] Record interventions, latency, actual calls, retries, failures, revision effort and content usefulness; unknown usage/cost remains unknown.
- [ ] Critical defects stop the affected scope immediately. Non-critical refinements do not block an otherwise useful safe pilot.
- [ ] Founder reviews usefulness; passing technical gates alone does not establish editorial value.

Exit: repeatable useful operation evidence; zero unresolved release-blocking defects. No fabricated calendar deadline or completion percentage.

### Remaining F6.1/F6.3 + F8 - improve after use

- [ ] Add only the highest-burden observed Board/search/filter/history improvements using canonical data, not invented fields from an image.
- [ ] Retain sanitized representative successes/failures and a separate holdout set; do not tune only to the pricing example.
- [ ] Each defect follows report -> isolated reproduction -> focused fix -> regression -> reviewed PR -> Founder merge/release -> observation.
- [ ] Measure first-pass usable output, edit burden, technical interventions and calls/time before accepting an optimization.
- [ ] Never edit live software, weaken checks, overwrite failed artifacts or let an operator approve its own changes.

## Merge and work scheduling

Review/reconcile #106 now on its docs branch; Founder may merge only after docs CI/review. This does not change #105's accepted implementation scope. F4/#105 remains the only active runtime implementation. If the base changes, recheck the integration candidate explicitly without assuming old exact-head evidence automatically transfers.

After F4: F5.1 -> AO-1 -> F5.2 -> AO-2 -> minimum F6 -> O1 -> F7. Prefer one coherent implementation PR per package; O1/F7 may be task/evidence records, not artificial code PRs. While waiting for Local proof, MG prepares next-package contracts/tests; it does not touch the frozen candidate.

Every package closes with: exact code and CI evidence; relevant local proof; no unauthorized side effects; one updated context/task entry; a clear Founder merge/release disposition. Design-ready, implemented, tested, deployed and production-proven remain separate labels.

Sources: merged finish-first plan/#101; #104 F3 acceptance; #105 current F4 contract and comments 5710443863, 5710760826, 5710896953; Spec 21/#106 delivery and acceptance documents; Founder-relayed A5 and A5R-B0.2 reports. The acceleration rules above are MG's delivery proposal, not a claim of work already executed.
