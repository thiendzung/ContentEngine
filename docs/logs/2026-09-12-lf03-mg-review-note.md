# LF-03 — MG gate note

Date: 2026-09-12

MG accepts the LF-02 Founder Angle approval evidence as PASS. The exact approval is canonical and no Outline runtime records existed at closeout.

LF-03 deliberately reuses the existing production `generate_real_o4_outline.py` entrypoint instead of adding code or a new workflow. The task removes the historical second identical execution/idempotency proof from the M1 critical path: finish the useful real Journal first; prove broader replay/idempotency in the later repeatability work unless an observed defect requires earlier intervention.

The current Outline implementation already permits a bounded maximum of two model attempts for structured-output validation. LF-03 authorizes only one outer CLI execution. If that execution fails, stop and classify before any retry because the current CLI may transition the run to terminal `failed` after generation failure.

The previous shell-path diagnostic is handled narrowly by the one-command PATH prefix to the already verified ChatGPT-bundled Codex executable. This is not an install, symlink, provider change or safeguard bypass.

On successful generation, stop at the mandatory Outline human gate. Writers remain blocked until Founder explicitly approves the persisted Outline.
