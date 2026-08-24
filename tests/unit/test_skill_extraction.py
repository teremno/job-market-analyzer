from dataclasses import FrozenInstanceError

import pytest

from job_market_analyzer.intelligence import (
    SKILL_TAXONOMY,
    SKILL_TAXONOMY_VERSION,
    EvidenceField,
    MatchKind,
    MentionKind,
    extract_skills,
)


def skill_codes(
    title: str = "",
    description_text: str | None = None,
    source_tags: tuple[str, ...] = (),
) -> tuple[str, ...]:
    return tuple(
        evidence.skill_code
        for evidence in extract_skills(title, description_text, source_tags)
    )


def test_taxonomy_v2_has_unique_stable_contracts() -> None:
    skill_codes_in_taxonomy = [skill.code for skill in SKILL_TAXONOMY]
    rule_ids = [
        alias.rule_id
        for skill in SKILL_TAXONOMY
        for alias in skill.aliases
    ]

    assert SKILL_TAXONOMY_VERSION == "4"
    assert len(SKILL_TAXONOMY) == 122
    assert skill_codes_in_taxonomy == sorted(skill_codes_in_taxonomy)
    assert len(skill_codes_in_taxonomy) == len(set(skill_codes_in_taxonomy))
    assert len(rule_ids) == len(set(rule_ids))
    assert all(skill.aliases for skill in SKILL_TAXONOMY)


@pytest.mark.parametrize(
    ("text", "skill_code", "rule_id"),
    [
        ("postgres", "postgresql", "postgresql.postgres"),
        ("PostgreSQL", "postgresql", "postgresql.postgresql"),
        ("nodejs", "nodejs", "nodejs.nodejs"),
        ("Node.js", "nodejs", "nodejs.node_dot_js"),
        (".NET", "dotnet", "dotnet.dotnet"),
        ("pytest", "pytest", "pytest.pytest"),
        ("py test", "pytest", "pytest.py_test"),
        ("ethers.js", "ethersjs", "ethersjs.ethers_dot_js"),
        ("web3.js", "web3js", "web3js.web3_dot_js"),
    ],
)
def test_supported_aliases_map_to_canonical_skills(
    text: str,
    skill_code: str,
    rule_id: str,
) -> None:
    evidence = extract_skills("", text, ())

    assert len(evidence) == 1
    assert evidence[0].skill_code == skill_code
    assert evidence[0].rule_id == rule_id
    assert evidence[0].matched_alias == text


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("Bash shell", "bash"),
        ("Cosmos SDK", "cosmos"),
        ("CSS3", "css"),
        ("EVM", "evm"),
        ("Figma AI", "figma"),
        ("Grafana", "grafana"),
        ("HTML5", "html"),
        ("Apache Kafka", "kafka"),
        ("Kafka Streams", "kafka"),
        ("Linux", "linux"),
        ("Prometheus monitoring", "prometheus"),
        ("React Native", "react_native"),
        ("Snowflake Data Cloud", "snowflake"),
        ("Snowflake warehouse", "snowflake"),
        ("Solana SDK", "solana"),
    ],
)
def test_taxonomy_v2_direct_aliases(
    text: str,
    expected_code: str,
) -> None:
    assert skill_codes("", text) == (expected_code,)


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("Bash scripting", "bash"),
        ("Blockchain nodes built with Cosmos", "cosmos"),
        ("Kafka or similar streaming platforms", "kafka"),
        ("Monitoring and observability with Prometheus", "prometheus"),
        ("Data warehouse workloads on Snowflake", "snowflake"),
        ("You are fluent in Figma for product design", "figma"),
        ("Principal Security Engineer working on Solana", "solana"),
    ],
)
def test_taxonomy_v2_contextual_aliases_require_technical_context(
    text: str,
    expected_code: str,
) -> None:
    evidence = extract_skills("", text, ())

    assert expected_code in {item.skill_code for item in evidence}
    assert next(
        item for item in evidence if item.skill_code == expected_code
    ).match_kind is MatchKind.CONTEXTUAL


@pytest.mark.parametrize(
    ("text", "excluded_code"),
    [
        ("Franz Kafka wrote novels in German", "kafka"),
        ("Prometheus is a figure in Greek mythology", "prometheus"),
        ("Paper snowflake decorations for winter", "snowflake"),
        ("Study the cosmos through a telescope", "cosmos"),
        ("Please bash the old box before recycling it", "bash"),
        ("Bash the old box before recycling it", "bash"),
        ("The cascading style of leadership matters", "css"),
        ("The fig machine arrived today", "figma"),
        ("Use a native reaction to the environment", "react_native"),
        ("Trusted by Meta, Figma, and Autodesk", "figma"),
        ("Track the current Solana price", "solana"),
        (
            "We advance the adoption and security of the Solana network",
            "solana",
        ),
        (
            "Solana Foundation is seeking a Senior IT Security Engineer",
            "solana",
        ),
    ],
)
def test_taxonomy_v2_ambiguous_or_partial_prose_is_rejected(
    text: str,
    excluded_code: str,
) -> None:
    assert excluded_code not in skill_codes("", text)


def test_taxonomy_v2_contextual_exact_source_tags_remain_direct_evidence() -> None:
    evidence = extract_skills("", None, ("Cosmos", "Kafka", "Prometheus", "Snowflake"))

    assert {item.skill_code for item in evidence} == {
        "cosmos",
        "kafka",
        "prometheus",
        "snowflake",
    }
    assert all(item.evidence_field is EvidenceField.TAG for item in evidence)
    assert all(item.match_kind is MatchKind.EXACT_ALIAS for item in evidence)


def test_taxonomy_v2_longer_aliases_do_not_infer_contained_skills() -> None:
    assert skill_codes("", "Ethereum Virtual Machine and React Native") == (
        "evm",
        "react_native",
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Bash scripting", ("bash",)),
        ("EVM", ("evm",)),
        ("Kafka Streams", ("kafka",)),
        ("React Native", ("react_native",)),
    ],
)
def test_taxonomy_v2_direct_mentions_do_not_infer_related_skills(
    text: str,
    expected: tuple[str, ...],
) -> None:
    assert skill_codes("", text) == expected


def test_sql_does_not_match_inside_postgresql_or_nosql() -> None:
    evidence = extract_skills("", "PostgreSQL and NoSQL storage", ())

    assert "postgresql" in {item.skill_code for item in evidence}
    assert "sql" not in {item.skill_code for item in evidence}


def test_git_does_not_match_partial_words_or_github_actions() -> None:
    evidence = extract_skills("", "Digital systems with GitHub Actions", ())

    assert skill_codes("", "Digital systems with GitHub Actions") == (
        "github_actions",
    )
    assert all(item.skill_code != "git" for item in evidence)


def test_c_cpp_and_csharp_do_not_collide() -> None:
    assert set(skill_codes("C, C++ and C# developer")) == {"c", "cpp", "csharp"}


def test_punctuation_aware_framework_aliases() -> None:
    assert set(
        skill_codes("", "Node.js services on ASP.NET with CI/CD")
    ) == {"cicd", "dotnet", "nodejs"}


def test_dot_suffix_does_not_turn_framework_names_into_javascript_evidence() -> None:
    assert set(
        skill_codes("", "Node.js, Next.js, Ethers.js and Web3.js")
    ) == {"ethersjs", "nextjs", "nodejs", "web3js"}


@pytest.mark.parametrize("text", ["Node.js", "NodeJS", "Node JS"])
def test_nodejs_aliases_do_not_create_javascript_evidence(text: str) -> None:
    assert skill_codes("", text) == ("nodejs",)


@pytest.mark.parametrize("text", ["JavaScript", "JS"])
def test_direct_javascript_aliases_still_resolve(text: str) -> None:
    assert skill_codes("", text) == ("javascript",)


@pytest.mark.parametrize(
    ("text", "excluded_skill"),
    [
        ("Ready to go build your career with us", "go"),
        ("Go to production after approval", "go"),
        ("We use go to market plans", "go"),
        ("Python and go to production", "go"),
        ("We operate a blockchain node and a tree node", "nodejs"),
        ("We react quickly to changing customer needs", "react"),
        ("JavaScript and react quickly", "react"),
        ("SQL and C grade performance", "c"),
        ("Remove rust corrosion from metal surfaces", "rust"),
        ("Vitamin C is listed in the benefits plan", "c"),
        ("Industrial foundry material specialist", "foundry"),
    ],
)
def test_ambiguous_terms_do_not_create_false_positive_skills(
    text: str,
    excluded_skill: str,
) -> None:
    assert excluded_skill not in skill_codes("", text)


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("Go developer", "go"),
        ("Go engineer", "go"),
        ("Go programming", "go"),
        ("Go language", "go"),
        ("must know Go", "go"),
        ("experience with Go", "go"),
        ("experience in Go", "go"),
        ("services written in Go", "go"),
        ("building services in Go", "go"),
        ("experience building services in Go", "go"),
        ("React developer", "react"),
        ("React engineer", "react"),
        ("React experience", "react"),
        ("experience with React", "react"),
        ("React framework", "react"),
        ("React.js", "react"),
        ("C developer", "c"),
        ("C engineer", "c"),
        ("C programming", "c"),
        ("C language", "c"),
        ("experience with C", "c"),
        ("Rust developer", "rust"),
        ("Rust engineer", "rust"),
        ("Rust programming", "rust"),
        ("Rust language", "rust"),
        ("experience with Rust", "rust"),
        ("Built in Rust and Solidity", "rust"),
    ],
)
def test_ambiguous_language_and_framework_names_require_safe_context(
    text: str,
    expected_code: str,
) -> None:
    assert expected_code in skill_codes("", text)


@pytest.mark.parametrize(
    "text",
    [
        "Foundry smart contract tooling",
        "Foundry for Solidity development",
        "Ethereum development with Foundry",
        "Build Ethereum smart contracts using Hardhat, Foundry and Ethers.js",
    ],
)
def test_foundry_requires_strong_web3_tooling_context(text: str) -> None:
    assert "foundry" in skill_codes("", text)


@pytest.mark.parametrize(
    "text",
    [
        "Use Palantir Foundry to analyze Ethereum transactions",
        "data foundry for Web3 analytics",
        "Foundry experience",
        "Foundry framework",
    ],
)
def test_non_web3_or_ambiguous_foundry_context_is_rejected(text: str) -> None:
    assert "foundry" not in skill_codes("", text)


@pytest.mark.parametrize(
    ("text", "excluded_skill"),
    [
        ("point de vue", "vue"),
        ("angular velocity", "angular"),
        ("laboratory flask", "flask"),
        ("wear a hardhat", "hardhat"),
        ("azure background color", "azure"),
        ("Travel across Java and Bali", "java"),
    ],
)
def test_unsafe_bare_aliases_reject_nontechnical_prose(
    text: str,
    excluded_skill: str,
) -> None:
    assert excluded_skill not in skill_codes("", text)


@pytest.mark.parametrize(
    ("text", "expected_skill"),
    [
        ("Angular framework", "angular"),
        ("AngularJS", "angular"),
        ("Angular developer", "angular"),
        ("Microsoft Azure", "azure"),
        ("Azure cloud engineer", "azure"),
        ("Python Flask", "flask"),
        ("Flask framework", "flask"),
        ("Hardhat framework", "hardhat"),
        ("Hardhat for Solidity development", "hardhat"),
        ("Java developer", "java"),
        ("Java programming", "java"),
        ("Java experience", "java"),
        ("Vue.js", "vue"),
        ("VueJS", "vue"),
        ("Vue developer", "vue"),
    ],
)
def test_ambiguous_bare_aliases_accept_explicit_technical_context(
    text: str,
    expected_skill: str,
) -> None:
    assert expected_skill in skill_codes("", text)


def test_python_flask_preserves_both_direct_mentions() -> None:
    assert skill_codes("", "Python Flask") == ("flask", "python")


def test_ambiguous_bare_source_tags_remain_direct_tag_evidence() -> None:
    expected = {"angular", "azure", "flask", "hardhat", "java", "vue"}

    evidence = extract_skills("", None, ("Angular", "Azure", "Flask", "Hardhat", "Java", "Vue"))

    assert {item.skill_code for item in evidence} == expected
    assert all(item.evidence_field is EvidenceField.TAG for item in evidence)
    assert all(item.match_kind is MatchKind.EXACT_ALIAS for item in evidence)


def test_ambiguous_alias_inside_a_general_source_tag_is_not_skill_evidence() -> None:
    # "go to market" became a direct v3 skill alias, so this guard test uses a
    # phrase that is still taxonomy-foreign even though its words overlap with
    # known aliases.
    assert extract_skills("", None, ("market strategy view", "point de vue")) == ()


@pytest.mark.parametrize("version", ["11", "14", "17", "20", "23"])
def test_cpp_numeric_standard_suffix_is_accepted(version: str) -> None:
    assert skill_codes("", f"C++{version} developer") == ("cpp",)


@pytest.mark.parametrize("text", ["C++Builder", "C+++", "C++17x"])
def test_cpp_malformed_extensions_are_rejected(text: str) -> None:
    assert "cpp" not in skill_codes("", text)


@pytest.mark.parametrize("text", ["CI/CD", "CI / CD", "CICD"])
def test_cicd_direct_aliases_are_supported(text: str) -> None:
    assert skill_codes("", text) == ("cicd",)


def test_same_skill_is_preserved_once_per_evidence_field() -> None:
    evidence = extract_skills(
        "Python Developer",
        "Python services tested with Python tooling",
        ("Python",),
    )
    python_evidence = [item for item in evidence if item.skill_code == "python"]

    assert [item.evidence_field for item in python_evidence] == [
        EvidenceField.TITLE,
        EvidenceField.DESCRIPTION,
        EvidenceField.TAG,
    ]


def test_repeated_and_multiple_aliases_keep_one_earliest_field_evidence() -> None:
    evidence = extract_skills(
        "",
        "Postgres, PostgreSQL, and postgres support Postgres workloads",
        (),
    )

    assert len(evidence) == 1
    assert evidence[0].skill_code == "postgresql"
    assert evidence[0].matched_alias == "Postgres"
    assert evidence[0].rule_id == "postgresql.postgres"


def test_source_tags_use_taxonomy_mapping_and_ignore_unknown_values() -> None:
    evidence = extract_skills(
        "",
        None,
        ("UnknownChain", "Docker", "Go", "React", "Foundry", "C"),
    )

    assert {item.skill_code for item in evidence} == {
        "c",
        "docker",
        "foundry",
        "go",
        "react",
    }
    assert all(item.evidence_field is EvidenceField.TAG for item in evidence)
    assert all(item.match_kind is MatchKind.EXACT_ALIAS for item in evidence)


def test_source_tag_input_order_does_not_change_output() -> None:
    first = extract_skills("", None, ("Python", "Docker", "Postgres"))
    second = extract_skills("", None, ("Postgres", "Python", "Docker"))

    assert first == second


@pytest.mark.parametrize(
    ("text", "direct_skill", "not_inferred_skill"),
    [
        ("FastAPI", "fastapi", "python"),
        ("React", None, "javascript"),
        ("Node.js", "nodejs", "javascript"),
        ("PostgreSQL", "postgresql", "sql"),
        ("Hardhat", None, "ethereum"),
        ("Kubernetes", "kubernetes", "docker"),
        ("S3 / EC2 / Lambda", None, "aws"),
    ],
)
def test_direct_mentions_do_not_infer_parent_or_dependency_skills(
    text: str,
    direct_skill: str | None,
    not_inferred_skill: str,
) -> None:
    extracted = set(skill_codes("", text))

    if direct_skill is not None:
        assert direct_skill in extracted
    assert not_inferred_skill not in extracted


def test_output_is_immutable_and_has_mentioned_semantics() -> None:
    evidence = extract_skills("Postgres Engineer", None, ())[0]

    assert evidence.evidence_field is EvidenceField.TITLE
    assert evidence.match_kind is MatchKind.EXACT_ALIAS
    assert evidence.mention_kind is MentionKind.MENTIONED
    assert evidence.evidence_text == "Postgres Engineer"
    with pytest.raises(FrozenInstanceError):
        evidence.skill_code = "changed"  # type: ignore[misc]


def test_empty_and_unknown_inputs_return_no_evidence() -> None:
    assert extract_skills("", None, ()) == ()
    assert extract_skills("", "QuantumFlux proprietary platform", ()) == ()


def test_unicode_context_and_snippet_are_preserved_safely() -> None:
    description = (
        "Шукаємо інженера для міжнародної команди. "
        "Досвід із Python та Docker потрібен для сервісів. "
        "Комунікація українською та англійською."
    )

    evidence = extract_skills("", description, ())
    python = next(item for item in evidence if item.skill_code == "python")

    assert "Шукаємо" in python.evidence_text
    assert "Python" in python.evidence_text
    assert len(python.evidence_text) <= 120
    assert len(python.evidence_text) < len(description)


def test_evidence_snippet_replaces_non_printable_control_characters() -> None:
    evidence = extract_skills("", "Use Python\x1b[31m safely", ())

    assert evidence[0].evidence_text == "Use Python�[31m safely"


def test_evidence_snippet_uses_tabs_and_newlines_as_word_boundaries() -> None:
    description = (
        "prefixword" * 10
        + "\tContext before Python after context\n"
        + "suffixword" * 10
    )

    evidence = extract_skills("", description, ())[0]

    assert evidence.evidence_text == "…Context before Python after context…"
    assert len(evidence.evidence_text) <= 120


def test_repeated_calls_have_identical_ordered_output() -> None:
    inputs = (
        "Python and React Developer",
        "Build PostgreSQL APIs with Docker, GraphQL and TypeScript.",
        ("AWS", "Python", "React"),
    )

    first = extract_skills(*inputs)
    second = extract_skills(*inputs)
    field_order = {
        EvidenceField.TITLE: 0,
        EvidenceField.DESCRIPTION: 1,
        EvidenceField.TAG: 2,
    }

    assert first == second
    assert list(first) == sorted(
        first,
        key=lambda item: (item.skill_code, field_order[item.evidence_field]),
    )


@pytest.mark.parametrize(
    ("title", "description", "tags", "expected"),
    [
        (
            "Backend Python Developer",
            "Build REST APIs with FastAPI, PostgreSQL and Docker.",
            (),
            {"docker", "fastapi", "postgresql", "python", "rest_api"},
        ),
        (
            "React Frontend Engineer",
            "Ship TypeScript applications with Next.js.",
            (),
            {"nextjs", "react", "typescript"},
        ),
        (
            "DevOps Engineer",
            "Manage Kubernetes on AWS with Terraform and GitHub Actions CI/CD.",
            ("Docker",),
            {"aws", "cicd", "docker", "github_actions", "kubernetes", "terraform"},
        ),
        (
            "Solidity Engineer",
            "Build Ethereum smart contracts using Hardhat, Foundry and Ethers.js.",
            ("Web3.js", "DeFi"),
            {"defi", "ethereum", "ethersjs", "foundry", "hardhat", "solidity", "web3js"},
        ),
        (
            "Machine Learning Engineer",
            "Train Python models with PyTorch and TensorFlow.",
            (),
            {"machine_learning", "python", "pytorch", "tensorflow"},
        ),
    ],
)
def test_realistic_job_examples(
    title: str,
    description: str,
    tags: tuple[str, ...],
    expected: set[str],
) -> None:
    assert set(skill_codes(title, description, tags)) == expected
