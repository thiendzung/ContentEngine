# CE05 T05.10 — Real O4 Outline closeout

Date: 2026-09-10
Status: **PASS**
Reviewer: **MG Content Engine**

## Exact accepted lineage

```text
ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808
Selected Angle: angle-01
AngleApproval: cebc0f94-77f9-4655-9141-41cd8a5dfc14
Outline Artifact: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1
Outline hash: 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
ContextManifest: 9b59c295-a956-4108-829b-63da711f1a54
ContextManifest hash: 48ffc7e925b2693fa1271f8d6c4b2254990be8920e8ff6e417e5e8e2cb0a4171
Prompt: journal_outline:v1
Recipe: journal_outline_v1:v1
Provider/model: codex_cli / gpt-5.6-luna
```

## Runtime evidence

- real Outline model execution: `1`;
- immutable `journal_outline` artifact persisted;
- identical second execution returned the same artifact with `model_attempts=0`;
- no extra ModelCall, ContextManifest, StepRun or Artifact on exact retry;
- ToolCall count remained `0`;
- ContentRun returned to `waiting_approval`;
- SettingsSnapshot remained unchanged;
- EvidenceSet, OriginalityPack, NeedHypothesis, Angle artifact and AngleApproval remained unchanged.

## Editorial gate

MG reviewed the full Outline and marked it **PASS** for T05.11/T05.12.

The accepted reader path is:

```text
work itself
→ practical costs
→ availability without urgency
→ price context
→ questions to ask
→ calm personal decision
```

Support mapping is accepted:

- MOTGU-original sections use the approved `ORIG-01…04` material;
- factual price-context section stays within the approved Smithsonian/MCI evidence;
- factual appraisal-context section stays within the approved IRS evidence;
- the Outline does not claim a universal fair price or valuation formula.

## Hard writer guard

T05.11/T05.12 must not turn `current price`, `sale status`, `physical location`, specific artwork identity, artist intent or other live commerce details into facts about a particular artwork unless exact canonical live data is explicitly present in the Writer input.

The current accepted input does **not** contain approved artwork-specific/artist-specific facts. Writers must remain at the approved first-time-buyer guidance level. If a new factual claim is needed, it must be declared unresolved rather than invented.

## Next gate

```text
T05.11 vi-VN writer
+
T05.12 en writer independently from Vietnamese
→ real bilingual draft review
```

English and Vietnamese are sibling drafts from the same accepted Outline. Neither is a translation source for the other.
