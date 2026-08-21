from dataclasses import FrozenInstanceError

import pytest

from job_market_analyzer.intelligence import (
    ROLE_CODES,
    ROLE_TAXONOMY_VERSION,
    RoleEvidenceField,
    RoleMatchKind,
    extract_roles,
)


def role_codes(
    title: str,
    description_text: str | None = None,
) -> tuple[str, ...]:
    return tuple(
        evidence.role_code for evidence in extract_roles(title, description_text)
    )


def test_role_taxonomy_v1_has_unique_stable_contracts() -> None:
    assert ROLE_TAXONOMY_VERSION == "1"
    assert len(ROLE_CODES) == 19
    assert list(ROLE_CODES) == sorted(ROLE_CODES)
    assert len(ROLE_CODES) == len(set(ROLE_CODES))
    assert "other" not in ROLE_CODES
    assert "unknown" not in ROLE_CODES


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("AI Engineer", ("ai_ml",)),
        ("Machine Learning Engineer", ("ai_ml",)),
        ("Senior Backend Software Developer", ("backend",)),
        ("Smart Contract Engineer", ("blockchain_protocol",)),
        ("Solidity Protocol Engineer", ("blockchain_protocol",)),
        ("Community Manager", ("community",)),
        ("Blockchain Data Engineer", ("data",)),
        ("Product Designer", ("design",)),
        ("Site Reliability Engineer", ("devops_platform",)),
        ("VP of Finance", ("finance",)),
        ("Quant Developer", ("finance",)),
        ("Front-end Developer", ("frontend",)),
        ("Senior Full Stack Engineer", ("full_stack",)),
        ("Senior Legal Counsel", ("legal_compliance",)),
        ("Growth Marketing Manager", ("marketing_growth",)),
        ("Head of Marketing (Director)", ("marketing_growth",)),
        ("Senior/Staff React Native Engineer", ("mobile",)),
        ("Chief Operating Officer", ("operations",)),
        ("Founding Product Manager", ("product",)),
        ("Quality Assurance Engineer", ("qa",)),
        ("Business Development Associate", ("sales_bd",)),
        ("Principal Security Engineer", ("security",)),
        ("Customer Support Specialist", ("support",)),
        ("Team Lead, Trust &amp; Safety Ops", ("support",)),
    ],
)
def test_strong_title_patterns_map_to_expected_roles(
    title: str,
    expected: tuple[str, ...],
) -> None:
    assert role_codes(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Product Design Lead", ("design",)),
        (
            "Machine Learning Platform Engineer",
            ("ai_ml", "devops_platform"),
        ),
        ("Data Platform Engineer", ("data", "devops_platform")),
        (
            "Senior Security Engineer - Infrastructure",
            ("devops_platform", "security"),
        ),
        ("Senior Software Engineer, Developer Platform", ("devops_platform",)),
        ("Social Media and Community Manager", ("community", "marketing_growth")),
        ("Support Operations", ("operations", "support")),
        (
            "Pioneer Program - Full Stack AI Engineer, Backend Oriented",
            ("ai_ml", "backend", "full_stack"),
        ),
        (
            "Binance Accelerator Program - Marketing BD Operations",
            ("marketing_growth", "operations", "sales_bd"),
        ),
    ],
)
def test_explicit_compound_titles_support_bounded_multi_label_results(
    title: str,
    expected: tuple[str, ...],
) -> None:
    assert role_codes(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Backend / Platform Engineer", ("backend", "devops_platform")),
        ("Backend | Platform Engineer", ("backend", "devops_platform")),
        ("Backend-Platform Engineer", ("backend", "devops_platform")),
        ("Senior Engineer (Backend)", ("backend",)),
        (
            "Security Engineer – Infrastructure",
            ("devops_platform", "security"),
        ),
        ("Dev Ops Engineer", ("devops_platform",)),
        ("Security Operations Analyst", ("security",)),
        ("Finance Manager", ("finance",)),
        ("Quant Researcher", ("finance",)),
        ("AML Analyst", ("legal_compliance",)),
        ("Sales Engineer", ("sales_bd",)),
    ],
)
def test_direct_functional_titles_support_safe_alias_and_punctuation_variants(
    title: str,
    expected: tuple[str, ...],
) -> None:
    assert role_codes(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Product Marketing Manager", ("marketing_growth",)),
        ("Security Product Manager", ("product",)),
        ("Data Product Manager", ("product",)),
        ("Platform Product Manager", ("product",)),
        ("AI Product Manager", ("product",)),
        ("Blockchain Marketing Manager", ("marketing_growth",)),
        ("Mobile Product Manager", ("product",)),
        ("Protocol Marketing Manager", ("marketing_growth",)),
        ("Protocol Partnerships Manager", ("sales_bd",)),
        ("Developer Community Manager", ("community",)),
        ("Product Council", ()),
    ],
)
def test_domain_and_department_modifiers_do_not_create_secondary_roles(
    title: str,
    expected: tuple[str, ...],
) -> None:
    assert role_codes(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Data Scientist", ("data",)),
        ("Analytics Engineer", ("data",)),
        ("Machine Learning Engineer", ("ai_ml",)),
        ("Applied Scientist", ("ai_ml",)),
        ("ML Platform Engineer", ("ai_ml", "devops_platform")),
        ("Data Platform Engineer", ("data", "devops_platform")),
        ("MLOps Engineer", ()),
    ],
)
def test_ai_ml_and_data_role_boundaries_are_explicit(
    title: str,
    expected: tuple[str, ...],
) -> None:
    assert role_codes(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Operations Manager", ("operations",)),
        ("Business Operations", ("operations",)),
        ("Support Operations", ("operations", "support")),
        ("Security Operations Analyst", ("security",)),
        ("DevOps Engineer", ("devops_platform",)),
        ("Developer Operations Engineer", ()),
        ("Product Operations Manager", ()),
        ("Marketing Operations Manager", ()),
        ("Sales Operations Manager", ()),
        ("Finance Operations Manager", ()),
        ("People Operations Manager", ()),
        ("Revenue Operations Manager", ()),
    ],
)
def test_specialized_operations_phrases_do_not_leak_into_general_operations(
    title: str,
    expected: tuple[str, ...],
) -> None:
    assert role_codes(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Smart Contract Developer", ("blockchain_protocol",)),
        ("Solidity Engineer", ("blockchain_protocol",)),
        ("Blockchain Protocol Developer", ("blockchain_protocol",)),
        ("Protocol Engineer", ()),
        ("Protocol Researcher", ()),
        ("Blockchain Product Manager", ("product",)),
        ("Crypto Operations", ()),
        ("Solana Marketing Manager", ("marketing_growth",)),
    ],
)
def test_blockchain_protocol_requires_engineering_function_evidence(
    title: str,
    expected: tuple[str, ...],
) -> None:
    assert role_codes(title) == expected


def test_full_stack_does_not_infer_frontend_or_backend() -> None:
    assert role_codes("Senior Full-Stack Software Engineer") == ("full_stack",)


@pytest.mark.parametrize(
    ("title", "description"),
    [
        (
            "Backend Engineer",
            "You will work closely with our frontend engineers and design team.",
        ),
        (
            "Product Manager",
            "Use Python and SQL while partnering with backend engineers.",
        ),
        (
            "QA Engineer",
            "Use Docker and collaborate with the DevOps Engineer.",
        ),
        (
            "Security Engineer",
            "Work closely with product managers and legal counsel.",
        ),
    ],
)
def test_strong_title_evidence_prevents_description_role_expansion(
    title: str,
    description: str,
) -> None:
    evidence = extract_roles(title, description)

    assert evidence
    assert all(item.evidence_field is RoleEvidenceField.TITLE for item in evidence)


def test_explicit_description_role_does_not_augment_strong_title() -> None:
    description = (
        "This is a platform engineering role responsible for infrastructure."
    )

    assert role_codes("Security Engineer", description) == ("security",)


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("We are looking for a Backend Engineer to own APIs.", ("backend",)),
        ("We are hiring a Frontend Developer to build interfaces.", ("frontend",)),
        ("Seeking a Machine Learning Engineer for model training.", ("ai_ml",)),
        ("Join our distributed team as a Product Designer.", ("design",)),
        ("Role: Senior Data Engineer\nBuild durable pipelines.", ("data",)),
        ("Position - Quality Assurance Engineer\nOwn release quality.", ("qa",)),
        (
            "The Role We are looking for a talented marketer to lead acquisition.",
            ("marketing_growth",),
        ),
        ("Job title: AML Analyst", ("legal_compliance",)),
    ],
)
def test_vague_titles_use_explicit_description_role_statements_only(
    description: str,
    expected: tuple[str, ...],
) -> None:
    evidence = extract_roles("Software Engineer", description)

    assert role_codes("Software Engineer", description) == expected
    assert all(
        item.evidence_field is RoleEvidenceField.DESCRIPTION for item in evidence
    )
    assert all(
        item.match_kind is RoleMatchKind.DESCRIPTION_STATEMENT for item in evidence
    )


@pytest.mark.parametrize(
    "description",
    [
        "Work closely with our frontend engineers.",
        "Collaborate with the Backend Engineer on APIs.",
        "Experience with React is useful for this role.",
        "Build mobile-friendly websites.",
        "Process large amounts of data.",
        "Use AI tools to create marketing content.",
        "Follow security best practices.",
        "Write unit tests and maintain Docker images.",
        "Support the internal sales team.",
        "Develop software for financial products.",
        "Work with product managers to define requirements.",
        "Partner with marketing managers on launches.",
        "Coordinate with security engineers.",
        "Liaise with legal counsel and compliance officers.",
        "Report to the Head of Data.",
        "Communicate with community managers.",
        "You will work closely with our Finance Manager.",
        "We are not hiring a Backend Engineer.",
        "We are no longer seeking a Product Manager.",
    ],
)
def test_incidental_description_language_does_not_create_roles(
    description: str,
) -> None:
    assert extract_roles("Engineer", description) == ()


@pytest.mark.parametrize(
    "title",
    [
        "Open Position",
        "Title TBD",
        "General Application",
        "Join Our Talent Network",
        "Engineer",
        "Consultant",
        "Member of Technical Staff Engineering",
        "Current Openings",
        "404",
        "Custom Role",
    ],
)
def test_unknown_is_represented_by_zero_evidence(title: str) -> None:
    assert extract_roles(title, None) == ()


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Web3 Marketing Manager", ("marketing_growth",)),
        ("Crypto Legal Counsel", ("legal_compliance",)),
        ("Blockchain Recruiter", ()),
        ("Web3 Developer", ()),
        ("Web3 Developer - Onchain Products", ()),
        ("Ethereum Foundation Role", ()),
        ("DeFi Analyst", ()),
        ("Tokenomics Researcher", ()),
        ("Product Lead (Blockchain)", ("product",)),
        ("Principal Security Engineer (Solana)", ("security",)),
        ("Blockchain Backend Engineer", ("backend",)),
        ("Senior Blockchain Engineer", ("blockchain_protocol",)),
        ("Remote Solidity Developer", ("blockchain_protocol",)),
    ],
)
def test_web3_terms_remain_domain_unless_title_names_protocol_work(
    title: str,
    expected: tuple[str, ...],
) -> None:
    assert role_codes(title) == expected


@pytest.mark.parametrize(
    "title",
    [
        "Junior Backend Developer",
        "Senior Backend Developer",
        "Staff Backend Engineer",
        "Principal Backend Engineer",
    ],
)
def test_seniority_terms_do_not_change_role_identity(title: str) -> None:
    assert role_codes(title) == ("backend",)


@pytest.mark.parametrize(
    ("title", "excluded_role"),
    [
        ("Frontend Engineer working with backend teams", "backend"),
        ("Backend Engineer working with frontend developers", "frontend"),
        ("Product Manager for a developer platform", "devops_platform"),
        ("Backend Engineer processing large amounts of data", "data"),
        ("Marketing Manager using AI tools", "ai_ml"),
        ("Backend Engineer following security best practices", "security"),
        ("Developer writing unit tests", "qa"),
        ("Web Developer building mobile-friendly websites", "mobile"),
        ("Frontend Engineer working from Figma designs", "design"),
        ("Engineer supporting the sales team", "sales_bd"),
        ("Engineer for financial products", "finance"),
        ("Software Engineer - Compliance", "legal_compliance"),
        ("DevOps Engineer", "operations"),
    ],
)
def test_role_words_and_skills_do_not_leak_into_unrelated_roles(
    title: str,
    excluded_role: str,
) -> None:
    assert excluded_role not in role_codes(title)


def test_role_evidence_is_immutable_bounded_and_explainable() -> None:
    description = (
        "Міжнародна команда шукає фахівця. "
        "We are looking for a Backend Engineer to build services. "
        + "Деталі " * 30
    )

    evidence = extract_roles("Engineer", description)[0]

    assert evidence.role_code == "backend"
    assert evidence.matched_text == "Backend Engineer"
    assert "Міжнародна" in evidence.evidence_text
    assert "Backend Engineer" in evidence.evidence_text
    assert len(evidence.evidence_text) <= 120
    with pytest.raises(FrozenInstanceError):
        evidence.role_code = "changed"  # type: ignore[misc]


def test_role_evidence_sanitizes_control_characters() -> None:
    evidence = extract_roles("Backend Engineer\x00", None)[0]

    assert evidence.matched_text == "Backend Engineer"
    assert evidence.evidence_text == "Backend Engineer�"


def test_repeated_calls_have_identical_code_order_and_evidence() -> None:
    title = "Machine Learning Platform Engineer"

    first = extract_roles(title, None)
    second = extract_roles(title, None)

    assert first == second
    assert [item.role_code for item in first] == sorted(
        item.role_code for item in first
    )


def test_source_tags_are_not_part_of_the_public_role_api() -> None:
    with pytest.raises(TypeError):
        extract_roles("Engineer", None, ("Backend",))  # type: ignore[call-arg]


def test_matcher_internals_are_not_exported_from_intelligence_package() -> None:
    import job_market_analyzer.intelligence as intelligence

    assert not hasattr(intelligence, "ROLE_TAXONOMY")
    assert not hasattr(intelligence, "RoleDefinition")
    assert not hasattr(intelligence, "RoleRule")
