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
