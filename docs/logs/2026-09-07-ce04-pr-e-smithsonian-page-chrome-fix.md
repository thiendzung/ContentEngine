# CE04 PR-E — Smithsonian page-chrome diagnosis and fix

Date: 2026-09-07

## Result that triggered this fix

The first direct-source Smithsonian supplement ran exactly once and respected the provider boundary:

- Serper = 0;
- Tavily = 0;
- Exa = 0;
- Jina = 1;
- EvidenceSet v6 remained draft/unlocked.

Human review rejected all 8 generated Evidence rows. Their excerpts matched the stored SourceDocument, but they were navigation/page-chrome rather than valuation guidance.

Result:

`BLOCKED — SMITHSONIAN SUPPLEMENT INSUFFICIENT`

## Root cause

The source itself is suitable and contains relevant artwork-value guidance, but Evidence extraction could rank navigation fragments above body prose because:

1. a segment containing multiple Markdown links was not rejected;
2. embedded Markdown images were rejected only when they appeared at the beginning of a segment;
3. navigation text contains many `artwork` / `artist` tokens and therefore could receive a high relevance score.

This is a claim-extraction/page-chrome bug. It is not a reason to weaken the source-quality Gate or change authority rules.

## Fix

`EvidenceResearchWorkflow._usable_statement()` now rejects:

- any candidate containing Markdown image syntax `![`;
- any candidate containing two or more Markdown links.

A single inline link remains allowed so useful prose with one citation is not discarded.

Regression coverage was added in:

`backend/tests/test_ce04_smithsonian_page_chrome.py`

The test mixes Smithsonian-like navigation/image fragments with relevant valuation prose and requires only the prose to survive extraction.

## Locked boundaries

Unchanged:

- NeedHypothesis-based subject anchoring;
- `.gov/.edu` conservative authority contract;
- Search snippets are not Evidence;
- no relation mutation;
- no lock during research;
- no fake ContentRun;
- quality Gate remains `>=2 useful supports / >=2 suitable independent domains`.

## Next

After canonical CI passes on the final head, rerun the same locked Smithsonian direct-source supplement exactly once.

This is a deterministic verification after an extractor bug fix, not a new search round.

If no direct O4 support survives after the fix, stop and keep PR-E blocked. Do not broaden research automatically.
