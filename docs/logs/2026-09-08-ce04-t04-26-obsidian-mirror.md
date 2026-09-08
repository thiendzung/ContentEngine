# CE04 T04.26 — Approved Knowledge Obsidian Mirror Closeout

Date: 2026-09-08
Branch: `ce04-knowledge-admission-provenance`
Start HEAD: `7c01b2c12021f112a231ffc85da83dcdf04d9caa`

## ContentRun inventory

Read-only inventory found four existing global ContentRuns:

| id | content_case_id | run_mode | status | created_at | updated_at |
|---|---|---|---|---|---|
| `eadb9bf9-d239-4033-a40c-0591aafdba26` | `86743645-9b26-4ec5-8e32-7180612dc729` | `create` | `pending` | `2026-09-06 08:40:18.998438+00` | `2026-09-06 08:40:18.998439+00` |
| `a4c39ece-1d7d-4049-b8d9-53ddcef091d4` | `1455d0b8-3ff1-4294-bf33-6a498497bf71` | `create` | `waiting_approval` | `2026-09-06 08:40:19.219651+00` | `2026-09-06 08:40:19.843278+00` |
| `41e85ecf-aeec-45e6-a658-ad5ca7c197f8` | `fd571af0-5041-465d-9921-1b92cead7535` | `create` | `pending` | `2026-09-08 03:18:55.540119+00` | `2026-09-08 03:18:55.540120+00` |
| `80dabda2-29fa-4a20-8e99-f6db684abf66` | `f6f3ba9a-dd9c-41d9-9bf3-83f144dbc456` | `create` | `pending` | `2026-09-08 03:19:14.013089+00` | `2026-09-08 03:19:14.013090+00` |

All four are `journal` runs for distinct synthetic ContentCases in project
`00000000-0000-0000-0000-000000000001`. Their linked opportunities all use the synthetic
question `Can work resume?` and synthetic NeedHypotheses (`Synthetic durable step ...`),
so none is the O4 ContentCase. O4 ContentCase
`9ec6133b-5f14-46d0-9866-e3b049e537b5` has exactly `0` ContentRuns.

No ContentRun was deleted or modified.

## T04.26 real mirror gate

- Temporary vault only: `/tmp/motgu-ce04-obsidian-gate`.
- Dry-run for both approved candidates: PASS; no files created.
- Exactly two approved files exported:
  - `10_Knowledge/08693242-d5c5-51b2-bde9-141c2933417d.md`
  - `10_Knowledge/1c9d6c34-91fe-5da2-af33-08a4dc39e2e2.md`
- SHA-256:
  - `08693242-d5c5-51b2-bde9-141c2933417d.md`: `d93ee29a88b69be0a526285643b6de423fc1c0fae848cb5e743bb488b9051344`
  - `1c9d6c34-91fe-5da2-af33-08a4dc39e2e2.md`: `40f14af25b41be3494721457c374a7614c71de36d300539dc037152c5d316471`
- Second export: byte-identical, same paths and hashes.
- Both rejected candidates were blocked with `candidate_status_not_exportable`.
- Exactly two Markdown files remain; no rejected ID, raw payload, raw response, HTML or page body is present.
- Provider calls: `0`.

## State and invariant correction

```text
global ContentRun: 4 → 4
O4 ContentCase ContentRun: 0 → 0
ContentRun mutation delta: 0
EvidenceSet v8: locked / unchanged
OriginalityPack: unchanged
NeedHypothesis: PROPOSED
ContentExperiment: PLANNED / PENDING
no rows deleted or repaired
```

The old fixed `ContentRun=2` invariant was stale. CE04 now verifies the scoped O4
ContentCase count and before/after delta; global count is environment-dependent. The
observed database drift strengthens the requirement for the T04.34 isolated test database.

T04.26 is `DONE`. T04.27–T04.35 remain `NOT STARTED`.

## Closeout boundary

No provider was called, no database row was changed, no personal Obsidian vault was used,
and T04.27 was not started.
