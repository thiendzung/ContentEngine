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

_COMMERCIAL_HINTS = (
    "/shop",
    "/store",
    "/product",
    "/products",
    "/booking",
    "checkout",
    "add-to-cart",
)
_SECOND_HOP_NOISE_HOSTS = (
    "facebook.com",
    "fbcdn.net",
    "fna.fbcdn.net",
    "twitter.com",
    "x.com",
    "pinterest.com",
    "linkedin.com",
    "blogger.com",
    "instagram.com",
    "cdninstagram.com",
    "youtube.com",
    "youtu.be",
)
_SECOND_HOP_NOISE_PATHS = ("/share", "/share-post", "/profile", "/login", "/signup")
_SECOND_HOP_NOISE_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js")
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
    parent_url: str | None = None,
) -> SourceCandidate:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().removeprefix("www.")
    commercial_haystack = f"{hostname} {parsed.path} {title}".lower()

    strong_institutional = hostname.endswith(".edu") or hostname.endswith(".gov")

    if strong_institutional:
        source_type = "institutional"
        bias = CommercialBias.LOW
        intended_use = IntendedUse.EVIDENCE_CANDIDATE
        why = "Public/academic institutional domain candidate; verify claim-level authority."
    elif hostname in {"reddit.com", "facebook.com", "tripadvisor.com"} or hostname.endswith(
        ".reddit.com"
    ):
        source_type = "community_or_review"
        bias = CommercialBias.UNKNOWN
        intended_use = IntendedUse.DISCOVERY
        why = "Community/review source; useful for market signals, not automatic factual authority."
    elif hostname == "artsy.net" or hostname.endswith(".artsy.net"):
        source_type = "editorial"
        bias = CommercialBias.MEDIUM
        intended_use = IntendedUse.DISCOVERY
        why = "Editorial art source; useful for discovery/context, verify claim-level authority."
    elif any(hint in commercial_haystack for hint in _COMMERCIAL_HINTS):
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
        parent_url=parent_url,
    )


def _prefer_duplicate_candidate(
    existing: SourceCandidate,
    candidate: SourceCandidate,
) -> SourceCandidate:
    """Keep the duplicate carrying stronger provenance; otherwise preserve first-seen order."""

    if (
        candidate.relation is SourceRelation.SECOND_HOP
        and existing.relation is not SourceRelation.SECOND_HOP
    ):
        return candidate
    if (
        candidate.parent_url is not None
        and existing.parent_url is None
        and candidate.relation is existing.relation
    ):
        return candidate
    return existing


def dedupe_sources(sources: Iterable[SourceCandidate]) -> list[SourceCandidate]:
    positions: dict[str, int] = {}
    result: list[SourceCandidate] = []
    for source in sources:
        key = source.url.rstrip("/").lower()
        position = positions.get(key)
        if position is None:
            positions[key] = len(result)
            result.append(source)
            continue
        result[position] = _prefer_duplicate_candidate(result[position], source)
    return result


def _source_host_key(source: SourceCandidate) -> str:
    return (urlparse(source.url).hostname or source.url).lower().removeprefix("www.")


def choose_sources(sources: Iterable[SourceCandidate], limit: int) -> list[SourceCandidate]:
    if limit <= 0:
        return []
    unique = dedupe_sources(sources)
    bias_order = {
        CommercialBias.LOW: 0,
        CommercialBias.UNKNOWN: 1,
        CommercialBias.MEDIUM: 2,
        CommercialBias.HIGH: 3,
    }
    source_type_order = {
        "institutional": 0,
        "editorial": 1,
        "review": 2,
        "community_or_review": 3,
        "editorial_or_unknown": 4,
        "commercial": 5,
        "unknown": 6,
    }
    # Python's sort is stable: preserve provider relevance/order within each quality bucket.
    unique.sort(
        key=lambda source: (
            source_type_order.get(source.source_type, 6),
            bias_order[source.commercial_bias],
        )
    )

    # First pass favors independent domains. A second pass fills any remaining capacity
    # without hiding useful same-domain candidates when the result set is small.
    selected: list[SourceCandidate] = []
    deferred: list[SourceCandidate] = []
    selected_hosts: set[str] = set()
    for source in unique:
        host = _source_host_key(source)
        if host in selected_hosts:
            deferred.append(source)
            continue
        selected.append(source)
        selected_hosts.add(host)
        if len(selected) >= limit:
            return selected

    for source in deferred:
        selected.append(source)
        if len(selected) >= limit:
            break
    return selected


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
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host == parent_host:
            continue
        normalized_host = host.removeprefix("www.")
        path = parsed.path.lower()
        if any(
            normalized_host == noise or normalized_host.endswith(f".{noise}")
            for noise in _SECOND_HOP_NOISE_HOSTS
        ) or any(noise in path for noise in _SECOND_HOP_NOISE_PATHS):
            continue
        if path.endswith(_SECOND_HOP_NOISE_SUFFIXES) or host.startswith(("static.", "scontent.")):
            continue
        candidate = annotate_source(
            provider="second_hop",
            query=query,
            url=url,
            title=url,
            snippet="Linked from selected source",
            found_via=f"linked_from:{parent_url}",
            relation=SourceRelation.SECOND_HOP,
            parent_url=parent_url,
        )
        candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates
