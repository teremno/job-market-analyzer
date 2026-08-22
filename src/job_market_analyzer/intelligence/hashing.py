"""Deterministic hashes for pure intelligence analyzer inputs."""

import hashlib
import json

from job_market_analyzer.models import normalize_source_tags


def _normalize_optional_description(description_text: str | None) -> str | None:
    return (
        None
        if description_text is None or not description_text.strip()
        else description_text
    )


def calculate_skill_input_hash(
    title: str,
    description_text: str | None,
    source_tags: tuple[str, ...],
) -> str:
    """Hash only the normalized fields consumed by ``extract_skills``."""

    analyzer_input = {
        "description_text": _normalize_optional_description(description_text),
        "source_tags": list(normalize_source_tags(source_tags)),
        "title": title,
    }
    serialized = json.dumps(
        analyzer_input,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def calculate_role_input_hash(
    title: str,
    description_text: str | None,
) -> str:
    """Hash only the normalized fields consumed by ``extract_roles``."""

    analyzer_input = {
        "description_text": _normalize_optional_description(description_text),
        "title": title,
    }
    serialized = json.dumps(
        analyzer_input,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def calculate_seniority_input_hash(title: str) -> str:
    """Hash only the normalized field consumed by ``extract_seniority``.

    Seniority v1 is a title-only analyzer; description changes intentionally
    do not create new seniority runs.
    """

    serialized = json.dumps(
        {"title": title},
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def calculate_geography_input_hash(
    description_text: str | None,
    *,
    location_text: str | None,
    is_remote: bool | None,
) -> str:
    """Hash only the normalized fields consumed by ``extract_geography``."""

    analyzer_input = {
        "description_text": _normalize_optional_description(description_text),
        "is_remote": is_remote,
        "location_text": _normalize_optional_description(location_text),
    }
    serialized = json.dumps(
        analyzer_input,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
