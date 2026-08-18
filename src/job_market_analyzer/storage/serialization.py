"""Deterministic serialization and hashing at the persistence boundary."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from job_market_analyzer.models import (
    NormalizedJobPosting,
    RawJob,
    normalize_source_tags,
)

SQLiteValue = str | int | None


def serialize_utc_datetime(value: datetime) -> str:
    """Serialize an aware datetime to the canonical SQLite UTC format."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")

    utc_value = value.astimezone(UTC)
    return utc_value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def serialize_decimal(value: Decimal) -> str:
    """Serialize a finite Decimal exactly without binary floating point."""

    if not value.is_finite():
        raise ValueError("decimal value must be finite")

    serialized = format(value, "f")

    if "." in serialized:
        serialized = serialized.rstrip("0").rstrip(".")

    if serialized in {"-0", "+0"}:
        return "0"

    return serialized


def serialize_raw_payload(payload: dict[str, Any]) -> str:
    """Serialize a JSON-like source payload deterministically for storage."""

    return _serialize_json(payload)


def serialize_source_tags(source_tags: tuple[str, ...]) -> str:
    """Serialize normalized source tags as compact canonical JSON."""

    return _serialize_json(list(source_tags))


def deserialize_source_tags(value: str) -> tuple[str, ...]:
    """Deserialize persisted source tags into their normalized domain form."""

    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise TypeError("source_tags_json must contain a JSON array")
    if any(not isinstance(tag, str) for tag in parsed):
        raise TypeError("source_tags_json array items must be strings")
    return normalize_source_tags(parsed)


def calculate_observation_hash(raw_job: RawJob) -> str:
    """Hash the source identity, URL, and payload of one raw observation."""

    observation = {
        "external_id": raw_job.external_id,
        "payload": raw_job.payload,
        "source_provider": raw_job.source_provider,
        "source_scope": raw_job.source_scope,
        "source_url": _serialize_optional_url(raw_job.source_url),
    }

    return _sha256(_serialize_json(observation))


def calculate_content_hash(posting: NormalizedJobPosting) -> str:
    """Hash the explicit normalized source-level fields persisted for a posting."""

    return _sha256(_serialize_json(serialize_normalized_posting(posting)))


def serialize_normalized_posting(
    posting: NormalizedJobPosting,
) -> dict[str, SQLiteValue]:
    """Serialize the explicit normalized fields stored on JobPosting."""

    return {
        "application_url": _serialize_optional_url(posting.application_url),
        "company_name": posting.company_name,
        "description_text": posting.description_text,
        "employment_type": _serialize_optional_enum(posting.employment_type),
        "external_id": posting.external_id,
        "is_remote": None if posting.is_remote is None else int(posting.is_remote),
        "location_text": posting.location_text,
        "published_at": _serialize_optional_datetime(posting.published_at),
        "remote_scope": _serialize_optional_enum(posting.remote_scope),
        "salary_currency": posting.salary_currency,
        "salary_max": _serialize_optional_decimal(posting.salary_max),
        "salary_min": _serialize_optional_decimal(posting.salary_min),
        "salary_period": _serialize_optional_enum(posting.salary_period),
        "salary_text": posting.salary_text,
        "source_provider": posting.source_provider,
        "source_scope": posting.source_scope,
        "source_tags_json": serialize_source_tags(posting.source_tags),
        "source_updated_at": _serialize_optional_datetime(posting.source_updated_at),
        "source_url": _serialize_optional_url(posting.source_url),
        "title": posting.title,
    }


def _serialize_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _serialize_optional_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None

    return serialize_utc_datetime(value)


def _serialize_optional_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None

    return serialize_decimal(value)


def _serialize_optional_enum(value: Enum | None) -> str | None:
    if value is None:
        return None

    return str(value.value)


def _serialize_optional_url(value: object | None) -> str | None:
    if value is None:
        return None

    return str(value)
