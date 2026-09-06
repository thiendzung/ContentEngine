import hashlib
import re
from dataclasses import replace

from app.modules.research.contracts import ResearchSpikeResult, SearchSignal
from app.modules.research.keyword_plan.contracts import (
    Signal,
    SignalProvenance,
    SignalScope,
    SignalSourceKind,
)

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^a-z0-9\s]+")


def normalize_text(value: str) -> str:
    lowered = value.casefold().strip()
    lowered = _NON_WORD_RE.sub(" ", lowered)
    return _SPACE_RE.sub(" ", lowered).strip()


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"{prefix}_{digest}"


def signal_fingerprint(*, locale: str, observed_text: str) -> str:
    return hashlib.sha256(
        f"{locale.casefold()}\x1f{normalize_text(observed_text)}".encode("utf-8")
    ).hexdigest()


def _search_signal_observation(signal: SearchSignal) -> str:
    if signal.text.strip():
        return signal.text.strip()
    if signal.title and signal.title.strip():
        return signal.title.strip()
    if signal.snippet and signal.snippet.strip():
        return signal.snippet.strip()
    return ""


def normalize_search_signals(
    result: ResearchSpikeResult,
    *,
    locale: str,
    artifact_ref: str | None = None,
) -> list[Signal]:
    normalized: list[Signal] = []
    for raw in result.signals:
        observed_text = _search_signal_observation(raw)
        if not observed_text:
            continue
        fingerprint = signal_fingerprint(locale=locale, observed_text=observed_text)
        signal_id = stable_id(
            "sig",
            SignalSourceKind.SEARCH.value,
            SignalScope.MARKET_WEB.value,
            locale,
            fingerprint,
            raw.provider,
            raw.query,
            raw.kind.value,
        )
        normalized.append(
            Signal(
                id=signal_id,
                source_kind=SignalSourceKind.SEARCH,
                scope=SignalScope.MARKET_WEB,
                observed_text=observed_text,
                locale=locale,
                context=f"{raw.kind.value}:{raw.query}",
                captured_at=result.created_at,
                provenance=SignalProvenance(
                    provider=raw.provider,
                    method=raw.kind.value,
                    artifact_ref=artifact_ref,
                    source_ref=raw.url,
                    locator=raw.query,
                ),
                fingerprint=fingerprint,
                source_url=raw.url,
                independence_group=fingerprint,
            )
        )
    return mark_duplicate_signals(normalized)


def make_observed_signal(
    *,
    source_kind: SignalSourceKind,
    scope: SignalScope,
    observed_text: str,
    locale: str,
    provider: str,
    method: str,
    context: str,
    captured_at: str,
    source_url: str | None = None,
    external_id: str | None = None,
    artifact_ref: str | None = None,
    locator: str | None = None,
) -> Signal:
    cleaned = observed_text.strip()
    if not cleaned:
        raise ValueError("observed_text_required")
    fingerprint = signal_fingerprint(locale=locale, observed_text=cleaned)
    return Signal(
        id=stable_id(
            "sig",
            source_kind.value,
            scope.value,
            locale,
            fingerprint,
            source_url or external_id or provider,
        ),
        source_kind=source_kind,
        scope=scope,
        observed_text=cleaned,
        locale=locale,
        context=context.strip(),
        captured_at=captured_at,
        provenance=SignalProvenance(
            provider=provider,
            method=method,
            artifact_ref=artifact_ref,
            source_ref=source_url or external_id,
            locator=locator,
        ),
        fingerprint=fingerprint,
        source_url=source_url,
        external_id=external_id,
        independence_group=fingerprint,
    )


def mark_duplicate_signals(signals: list[Signal]) -> list[Signal]:
    first_by_fingerprint: dict[str, str] = {}
    output: list[Signal] = []
    for signal in signals:
        first_id = first_by_fingerprint.get(signal.fingerprint)
        if first_id is None:
            first_by_fingerprint[signal.fingerprint] = signal.id
            output.append(signal)
            continue
        output.append(replace(signal, duplicate_of=first_id))
    return output


def unique_signals(signals: list[Signal]) -> list[Signal]:
    return [signal for signal in signals if signal.duplicate_of is None]
