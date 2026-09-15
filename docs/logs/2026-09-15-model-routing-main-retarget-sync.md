# Model Routing v1 — main retarget sync

Date: 2026-09-15

- Base retargeted to `main` after merged PR #99.
- Integrated main merge commit: `cf22d01274991b40b4f269ad79f1b361bcb8dcaa`.
- Runtime scope remains limited to Model Routing Policy v1 plus migration `20260915_0034`, tests, and documentation.
- No operational migration, active routing policy activation, external model execution, or production data mutation is authorized by this record.
- A fresh exact-head CI run is required before Ready for Review.
