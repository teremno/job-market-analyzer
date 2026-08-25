"""Gold-set FP/FN gate for the role taxonomy (R2).

Every ambiguous alias pinned here carries positive, negative, and guard
cases. Any ROLE_TAXONOMY_VERSION bump must keep this suite green before it
ships; add cases for every newly mined family in the same change.
"""

import pytest

from job_market_analyzer.intelligence.roles import (
    ROLE_TAXONOMY_VERSION,
    extract_roles,
)

GOLD_CASES: tuple[tuple[str, frozenset[str]], ...] = (
    # --- v3: solutions architecture family ---
    ("Solutions Architect", {"solutions_architect"}),
    ("Sr. Solutions Architect", {"solutions_architect"}),
    ("Delivery Solutions Architect", {"solutions_architect"}),
    (
        "Senior Solutions Architect (EDW Enterprise Data Warehouse Migrations)",
        {"solutions_architect"},
    ),
    # Pre-sales engineering stays sales-side; must NOT leak into solutions_*
    ("Solutions Engineer", {"sales_bd"}),
    ("Head of Solutions Engineering", {"sales_bd"}),
    # --- v3: delivery / forward-deployed family ---
    ("Forward Deployed Engineer", {"delivery_engineering"}),
    (
        "Forward Deployed Software Engineer, Internship - Commercial",
        {"delivery_engineering"},
    ),
    (
        "Sr. Forward Deployed Engineer (FDE) - Financial Services",
        {"delivery_engineering"},
    ),
    ("Manager, Forward Deployed Engineering", {"delivery_engineering"}),
    ("Deployment Strategist", {"delivery_engineering"}),
    ("Implementation Consultant", {"delivery_engineering"}),
    ("Professional Services Consultant", {"delivery_engineering"}),
    # --- v3: extended families ---
    ("Brand Designer", {"design"}),
    ("Database Reliability Engineer - Core Team", {"devops_platform"}),
    ("Commercial Counsel", {"legal_compliance"}),
    ("Events Manager | EMEA | Remote", {"marketing_growth"}),
    ("Executive Assistant to the CEO", {"operations"}),
    ("Partnerships Associate", {"sales_bd"}),
    ("Manager, Sales Development", {"sales_bd"}),
    ("Deal Operations Administrator", {"sales_bd"}),
    ("Sales Operations Manager", {"sales_bd"}),
    ("Revenue Accounting Manager", {"finance"}),
    ("AI Product Engineer - ClickStack", {"ai_ml"}),
    # --- one positive per remaining code keeps the coverage gate honest ---
    ("Smart Contract Engineer", {"blockchain_protocol"}),
    ("Developer Community Manager", {"community"}),
    ("Senior Data Engineer", {"data"}),
    ("Frontend Developer", {"frontend"}),
    ("Full Stack Engineer", {"full_stack"}),
    ("Senior/Staff React Native Engineer", {"mobile"}),
    ("Test Automation Engineer", {"qa"}),
    ("Customer Support Specialist", {"support"}),
    # --- long-standing guards that must survive every revision ---
    ("Security Operations Analyst", {"security"}),
    ("Site Reliability Engineer", {"devops_platform"}),
    ("Product Manager", {"product"}),
    ("Backend Engineer", {"backend"}),
    # --- deliberate Unknown boundaries (precision-first, ADR-021) ---
    ("Software Engineer", set()),
    ("Senior Software Engineer", set()),
    ("Staff Software Engineer", set()),
    ("Principal Software Engineer - Privacy", set()),
    ("Engineering Manager", set()),
)


def test_taxonomy_version_is_pinned_to_the_reviewed_revision() -> None:
    assert ROLE_TAXONOMY_VERSION == "3"


@pytest.mark.parametrize(("title", "expected_codes"), GOLD_CASES)
def test_gold_title_classifies_exactly_as_expected(
    title: str,
    expected_codes: frozenset[str] | set[str],
) -> None:
    evidence = extract_roles(title, None)
    assert {item.role_code for item in evidence} == set(expected_codes), (
        f"title={title!r} produced "
        f"{[(e.role_code, e.rule_id) for e in evidence]}"
    )


def test_gold_set_covers_every_current_role_code() -> None:
    covered = {
        code
        for _, codes in GOLD_CASES
        if codes
        for code in codes
    }
    from job_market_analyzer.intelligence.roles import ROLE_CODES

    missing = sorted(set(ROLE_CODES) - covered)
    assert not missing, f"role codes without any positive gold case: {missing}"
