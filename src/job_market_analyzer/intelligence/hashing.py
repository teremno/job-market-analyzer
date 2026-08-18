"""Deterministic hashes for pure intelligence analyzer inputs."""

import hashlib
import json

from job_market_analyzer.models import normalize_source_tags


def calculate_skill_input_hash(
    title: str,
    description_text: str | None,
    source_tags: tuple[str, ...],
) -> str:
    """Hash only the normalized fields consumed by ``extract_skills``."""

    normalized_description = (
        None
        if description_text is None or not description_text.strip()
        else description_text
    )
    analyzer_input = {
        "description_text": normalized_description,
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
