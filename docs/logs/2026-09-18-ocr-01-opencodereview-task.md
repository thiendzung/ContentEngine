# OCR-01 - OpenCodeReview advisory review contract

Issue: #119.

## Purpose

Use Alibaba OpenCodeReview as a second semantic reviewer for ContentEngine. OCR is advisory in OCR-01: it does not replace existing CI, MG review, Agent Local runtime proof, or Founder merge authority.

Default local mode is **Delegation Mode**: OCR performs deterministic file selection/rule resolution and the host coding agent performs the semantic review with its existing model subscription. Direct OCR-managed LLM review is optional and separately configured.

## Version and local execution

OCR-01 is reviewed against OpenCodeReview **v1.12.5** (latest verified release on 2026-09-18).

Run only from a clean checkout/worktree at the exact assigned ref. Do not modify the protected Founder checkout merely to run OCR. Base and head must be explicit commit refs; do not rely on a possibly stale local `main`.

If OCR is not installed, install the pinned release:

```sh
OCR_VERSION=v1.12.5 npm install -g @alibaba-group/open-code-review
```

Record `ocr version` and `git --version`. OpenCodeReview's integration documentation requires Git >= 2.41. A trial that happens to work on an older Git version is useful evidence, but it is not a supported local baseline. Upgrade the Agent Local OCR lane to Git >= 2.41 before relying on OCR for routine PR review.

If a materially different OCR version is already installed, do not silently treat its results as equivalent to the reviewed v1.12.5 behavior.

Do not store provider secrets in the repository.

## Default delegated review

Preview the exact review scope without an OCR-side LLM call:

```sh
make ocr-preview OCR_BASE=<EXACT_BASE_SHA> OCR_HEAD=<EXACT_HEAD_SHA>
```

This writes `artifacts/ocr/preview.json` and must report the exact range/merge-base, reviewable files and excluded files.

Then use the OpenCodeReview **delegation** workflow from the host coding agent for that exact range:

1. use `ocr delegate rule --format json` for the reviewable paths;
2. inspect the exact diffs from the previewed merge-base to `OCR_HEAD`;
3. review every previewed file against its resolved project rule and relevant surrounding context;
4. account for every reviewable file as reviewed or explicitly skipped;
5. return only grounded findings, prioritizing critical/high/medium.

The project config is `.opencodereview/rule.json`; bounded project context is `.opencodereview/background.md`.

## Optional direct OCR-managed review

Use only when an OCR LLM endpoint is intentionally configured:

```sh
make ocr-review-direct OCR_BASE=<EXACT_BASE_SHA> OCR_HEAD=<EXACT_HEAD_SHA>
```

This writes `artifacts/ocr/review.json`. Direct mode is not the default Agent Local path and does not authorize new provider credentials.

## Evidence returned to MG

Return:
- exact start/end HEAD and exact base/head refs;
- OCR version and Git version;
- preview total/reviewable/excluded files and merge-base;
- `artifacts/ocr/preview.json` retained locally;
- review coverage: reviewed files, skipped files with reason, coverage rate;
- all critical/high/medium findings with path, line, category and severity;
- any OCR error, unsupported CLI behavior, size/budget skip or rule-resolution failure;
- no code changes unless MG separately delegates a bounded fix.

MG classifies every finding as **true defect / missing test / false positive** before code changes. Low-severity style-only findings are not merge blockers.

## Boundaries

- no auto-fix;
- no auto-merge;
- no operational DB/model/content execution;
- no CI merge gate in OCR-01;
- no weakening existing pytest/mypy/ruff/frontend checks;
- no treating OCR PASS as runtime acceptance;
- no implicit `main` or moving ref accepted as exact review evidence.
