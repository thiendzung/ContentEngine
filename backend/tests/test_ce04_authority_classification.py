import pytest

from app.modules.research.contracts import CommercialBias
from app.modules.research.utils import annotate_source


@pytest.mark.parametrize(
    "url",
    [
        "https://museumexample.org/art-appraisal",
        "https://artassociation.org/artwork-appraisal",
        "https://valuationinstitute.net/art-guide",
        "https://artarchive.io/appraisal",
    ],
)
def test_brand_words_on_non_gov_edu_domains_do_not_create_authority(url: str) -> None:
    source = annotate_source(
        provider="serper",
        query="art appraisal",
        url=url,
        title="Artwork appraisal guide",
        snippet="Professional appraisal guidance.",
        found_via="google_organic",
    )

    assert source.source_type == "editorial_or_unknown"
    assert source.commercial_bias is CommercialBias.UNKNOWN
    assert source.intended_use.value == "discovery"


@pytest.mark.parametrize(
    "url",
    [
        "https://arts.gov/guide",
        "https://archive.example.gov.uk/guide",
        "https://collection.example.museum/guide",
        "https://agency.example.int/guide",
    ],
)
def test_public_institutional_domains_remain_automatic_evidence_candidates(
    url: str,
) -> None:
    source = annotate_source(
        provider="serper",
        query="art appraisal",
        url=url,
        title="Artwork appraisal guide",
        snippet="Professional appraisal guidance.",
        found_via="google_organic",
    )

    assert source.source_type == "institutional"
    assert source.commercial_bias is CommercialBias.LOW
    assert source.intended_use.value == "evidence_candidate"


@pytest.mark.parametrize(
    "url",
    [
        "https://museum.example.edu/art-appraisal",
        "https://museum.example.edu.vn/art-appraisal",
        "https://conservation.example.ac.uk/guide",
    ],
)
def test_educational_domains_remain_discovery_not_automatic_factual_authority(
    url: str,
) -> None:
    source = annotate_source(
        provider="serper",
        query="art appraisal",
        url=url,
        title="Artwork appraisal guide",
        snippet="Professional appraisal guidance.",
        found_via="google_organic",
    )

    assert source.source_type == "educational"
    assert source.commercial_bias is CommercialBias.LOW
    assert source.intended_use.value == "discovery"
