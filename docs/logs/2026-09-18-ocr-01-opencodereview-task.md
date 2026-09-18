# OCR-01 - OpenCodeReview advisory review contract

Issue: #119.

## Purpose

Use Alibaba OpenCodeReview as a second semantic reviewer for ContentEngine. OCR is advisory in OCR-01: it does not replace existing CI, MG review, Agent Local runtime proof, or Founder merge authority.

## Local execution

Run only from a clean checkout/worktree at the exact assigned ref. Do not modify the protected Founder checkout merely to run OCR.

Install the CLI only if the command is unavailable:

```sh
npm install -g @alibaba-group/open-code-review
```

Prefer the Codex plugin/delegation mode when available. Do not store provider secrets in the repository.

## Required commands

Preview the review scope without an LLM call:

```sh
make ocr-preview OCR_BASE=main OCR_HEAD=HEAD
```

Run advisory review and write machine-readable output under ignored local artifacts:

```sh
make ocr-review OCR_BASE=main OCR_HEAD=HEAD
```

The project config must come from `.opencodereview/rule.json` and project background from `.opencodereview/background.md`.

## Evidence returned to MG

Return:
- exact HEAD and base/head refs;
- OCR CLI version if available from normal command output;
- preview file count and skipped/warning summary;
- `artifacts/ocr/review.json` retained locally;
- all critical/high/medium findings with path, line, category and severity;
- any OCR execution error or files skipped because of budget/size;
- no code changes unless MG separately delegates a bounded fix.

MG classifies every finding as true defect / missing test / false positive before code changes. Low-severity style-only findings are not merge blockers.

## Boundaries

- no auto-fix;
- no auto-merge;
- no operational DB/model/content execution;
- no CI merge gate in OCR-01;
- no weakening existing pytest/mypy/ruff/frontend checks;
- no treating OCR PASS as runtime acceptance.
