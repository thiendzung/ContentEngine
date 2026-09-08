from app.modules.research.contracts import CommercialBias, SourceCandidate
from app.modules.research.utils import choose_sources


def _source(url: str) -> SourceCandidate:
    return SourceCandidate(
        provider="serper",
        query="q",
        url=url,
        title=url,
        source_type="editorial",
        commercial_bias=CommercialBias.LOW,
    )


def test_choose_sources_prefers_independent_domains_before_same_domain_fill() -> None:
    sources = [
        _source("https://alpha.example/one"),
        _source("https://alpha.example/two"),
        _source("https://beta.example/one"),
    ]

    selected = choose_sources(sources, 2)

    assert [source.url for source in selected] == [
        "https://alpha.example/one",
        "https://beta.example/one",
    ]
