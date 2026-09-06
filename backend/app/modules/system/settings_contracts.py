from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VoiceLevels(BaseModel):
    calm: Literal["low", "medium", "high"]
    intimate: Literal["low", "medium", "high"]
    poetic: Literal["low", "medium", "high"]
    commercial: Literal["low", "medium", "high"]
    academic: Literal["low", "medium", "high"]


class BrandDNA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: dict[str, str]
    voice: VoiceLevels
    boundaries: dict[str, list[str]]
    proof_preferences: dict[str, list[str]]


class LanguageDNA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locale: Literal["vi-VN", "en"]
    audience_context: str = Field(min_length=1)
    vocabulary: dict[str, object]
    rhythm: dict[str, object]
    sensory_language: dict[str, object]
    rhetorical_questions: dict[str, object]
    metaphor: dict[str, object]
    direct_answer: dict[str, object]
    cta: dict[str, object]

    @field_validator("locale")
    @classmethod
    def normalize_locale(cls, value: str) -> str:
        return value


def validate_brand_dna(value: dict[str, object]) -> BrandDNA:
    return BrandDNA.model_validate(value)


def validate_language_dna(value: dict[str, object]) -> LanguageDNA:
    return LanguageDNA.model_validate(value)
