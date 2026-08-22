import pytest

from job_market_analyzer.intelligence.seniority import (
    SENIORITY_TAXONOMY_VERSION,
    extract_seniority,
)


def test_taxonomy_version_is_v1() -> None:
    assert SENIORITY_TAXONOMY_VERSION == "1"


@pytest.mark.parametrize(
    ("title", "expected_code"),
    [
        ("Intern — Data Team", "intern"),
        ("Junior Backend Engineer", "junior"),
        ("Backend Engineer, graduate level", "junior"),
        ("Entry-Level QA Analyst", "junior"),
        ("Mid-level Product Designer", "mid"),
        ("Senior Software Engineer", "senior"),
        ("Sr. DevOps Engineer", "senior"),
        ("Lead Developer", "lead"),
        ("Engineering Lead - Payments", "lead"),
        ("Staff Software Engineer", "staff"),
        ("Principal Data Scientist", "principal"),
        ("Software Engineer", None),
        ("Web Developer", None),
        ("Product Manager", None),
        ("Customer Success Manager", None),
        # People-management words are not experience-level evidence in v1.
        ("Engineering Manager", None),
        ("Director of Engineering", None),
    ],
)
def test_title_classification(
    title: str,
    expected_code: str | None,
) -> None:
    evidence = extract_seniority(title)
    if expected_code is None:
        assert evidence == ()
    else:
        assert [item.seniority_code for item in evidence] == [expected_code]


def test_highest_rank_wins_when_multiple_signals_present() -> None:
    evidence = extract_seniority("Senior Staff Software Engineer")
    assert [item.seniority_code for item in evidence] == ["staff"]


def test_evidence_carries_rule_and_snippet() -> None:
    title = "Senior Software Engineer - Platform"
    evidence = extract_seniority(title)

    assert len(evidence) == 1
    item = evidence[0]
    assert item.rule_id == "senior.named"
    assert item.matched_text.casefold() == "senior"
    assert item.evidence_text.startswith("Senior")
    assert item.evidence_field.value == "title"
    assert item.match_kind.value == "title_pattern"


def test_repeated_calls_are_deterministic() -> None:
    title = "Junior Python Developer"
    assert extract_seniority(title) == extract_seniority(title)
