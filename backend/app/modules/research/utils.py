import ipaddress
import json
import re
from collections.abc import Iterable
from urllib.parse import urlparse

from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    SourceCandidate,
    SourceRelation,
)

_INSTITUTIONAL_HINTS = (
    ".edu",
    ".gov",
    "museum",
    "university",
    "institute",
    "institution",
    "foundation",
    "archive",
)
_COMMERCIAL_HINTS = (
    "/shop",
    "/store",
    "/product",
    "/products",
    "/booking",
    "checkout",
    "add-to-cart",
)
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")
_BARE_URL_RE = re.compile(r"https?://[^\s<>()\]\[\]{}\"']+")


def as_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def list_items(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def dict_items(value: object) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for item in list_items(value):
        parsed = as_dict(item)
        if parsed is not None:
            result.append(parsed)
    return result


def string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def suggestion_values(value: object) -> list[str]:
    result: list[str] = []
    for item in list_items(value):
        if isinstance(item, str):
            result.append(item)
            continue
        parsed = as_dict(item)
        if parsed is None:
            continue
        suggestion = (
            string_value(parsed.get("value"))
            or string_value(parsed.get("query"))
            or string_value(parsed.get("text"))
        )
        if suggestion:
            result.append(suggestion)
    return result


def int_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def bounded_json_excerpt(payload: object, max_chars: int) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 15]}...[truncated]"


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url_must_be_public_http")

    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("local_url_not_allowed")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return url

    if not address.is_global:
        raise ValueError("private_or_local_ip_not_allowed")
    return url


def annotate_source(
    *,
    provider: str,
    query: str,
    url: str,
    title: str,
    snippet: str,
    found_via: str,
    relation: SourceRelation = SourceRelation.DIRECT,
) -> SourceCandidate:
    parsed = urlparse(url)
    haystack = f"{parsed.hostname or ''} {parsed.path} {title}".lower()

    if any(hint in haystack for hint in _INSTITUTIONAL_HINTS):
        source_type = "institutional"
        bias = CommercialBias.LOW
        intended_use = IntendedUse.EVIDENCE_CANDIDATE
        why = (
            "Institutional/primary-looking source candidate; "
            "verify claim-level authority before use."
        )
    elif any(hint in haystack for hint in _COMMERCIAL_HINTS):
        source_type = "commercial"
        bias = CommercialBias.HIGH
        intended_use = IntendedUse.CONTEXT_ONLY
        why = (
            "Commercial source; useful for market/discovery context, "
            "not automatic factual authority."
        )
    else:
        source_type = "editorial_or_unknown"
        bias = CommercialBias.UNKNOWN
        intended_use = IntendedUse.DISCOVERY
        why = "Potentially relevant source; authority remains unverified until source review."

    return SourceCandidate(
        provider=provider,
        query=query,
        url=url,
        title=title or url,
        snippet=snippet,
        source_type=source_type,
        commercial_bias=bias,
        found_via=found_via,
        relation=relation,
        intended_use=intended_use,
        why_selected=why,
    )


def dedupe_sources(sources: Iterable[SourceCandidate]) -> list[SourceCandidate]:
    seen: set[str] = set()
    result: list[SourceCandidate] = []
    for source in sources:
        key = source.url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(source)
    return result


def choose_sources(sources: Iterable[SourceCandidate], limit: int) -> list[SourceCandidate]:
    unique = dedupe_sources(sources)
    bias_order = {
        CommercialBias.LOW: 0,
        CommercialBias.UNKNOWN: 1,
        CommercialBias.MEDIUM: 2,
        CommercialBias.HIGH: 3,
    }
    unique.sort(key=lambda source: (bias_order[source.commercial_bias], source.url))
    return unique[:limit]


def extract_second_hop_candidates(
    content: str,
    *,
    parent_url: str,
    query: str,
    limit: int,
    linked_urls: Iterable[str] = (),
) -> list[SourceCandidate]:
    if limit <= 0:
        return []
    parent_host = (urlparse(parent_url).hostname or "").lower()
    raw_urls = (
        list(linked_urls)
        + list(_MARKDOWN_LINK_RE.findall(content))
        + list(_BARE_URL_RE.findall(content))
    )
    candidates: list[SourceCandidate] = []
    seen: set[str] = set()

    for raw_url in raw_urls:
        url = raw_url.rstrip(".,;:")
        if url in seen:
            continue
        seen.add(url)
        try:
            validate_public_http_url(url)
        except ValueError:
            continue
        host = (urlparse(url).hostname or "").lower()
        if host == parent_host:
            continue
        candidate = annotate_source(
            provider="second_hop",
            query=query,
            url=url,
            title=url,
            snippet="Linked from selected source",
            found_via=f"linked_from:{parent_url}",
            relation=SourceRelation.SECOND_HOP,
        )
        candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates
