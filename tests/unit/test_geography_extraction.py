import pytest

from job_market_analyzer.intelligence.geography import (
    GEOGRAPHY_TAXONOMY_VERSION,
    extract_geography,
)


def test_taxonomy_version_is_v1() -> None:
    assert GEOGRAPHY_TAXONOMY_VERSION == "1"


def test_structured_remote_flag_is_authoritative() -> None:
    evidence = extract_geography(
        "Hybrid working model in our Berlin office serving the EU market.",
        location_text=None,
        is_remote=True,
    )
    arrangement = [item for item in evidence if item.dimension == "arrangement"]
    assert [item.geography_code for item in arrangement] == ["arrangement_remote"]
    assert arrangement[0].rule_id == "geography.arrangement.structured"
    assert arrangement[0].match_kind.value == "normalized_field"
    # Region evidence still works alongside the structured flag.
    assert any(item.geography_code == "region_europe" for item in evidence)


def test_structured_not_remote_yields_no_arrangement() -> None:
    evidence = extract_geography("Office-based role.", location_text=None, is_remote=False)
    assert all(item.dimension != "arrangement" for item in evidence)


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("This is a 100% remote position.", "arrangement_remote"),
        ("We are a fully remote team across timezones.", "arrangement_remote"),
        ("Remote-first company since day one.", "arrangement_remote"),
        (
            "Hybrid working model: two days per week in office.",
            "arrangement_hybrid",
        ),
        ("Work hybrid from our hubs.", "arrangement_hybrid"),
        ("This role is on-site in Krakow five days a week.", "arrangement_onsite"),
        ("Great salary and benefits package.", None),
    ],
)
def test_arrangement_from_text(description: str, expected: str | None) -> None:
    evidence = extract_geography(description, location_text=None, is_remote=None)
    arrangement = [
        item for item in evidence if item.dimension == "arrangement"
    ]
    if expected is None:
        assert arrangement == []
    else:
        assert [item.geography_code for item in arrangement] == [expected]


def test_full_remote_beats_hybrid_mention() -> None:
    evidence = extract_geography(
        "Fully remote company; some teams keep hybrid meetups occasionally.",
        location_text=None,
        is_remote=None,
    )
    arrangement = [item for item in evidence if item.dimension == "arrangement"]
    assert [item.geography_code for item in arrangement] == ["arrangement_remote"]


def test_regions_are_multi_label_with_location_priority() -> None:
    evidence = extract_geography(
        "You will collaborate with teams worldwide.",
        location_text="Europe (EU only)",
        is_remote=None,
    )
    regions = {
        item.geography_code: item for item in evidence if item.dimension == "region"
    }
    assert set(regions) == {"region_worldwide", "region_europe"}
    europe = regions["region_europe"]
    assert europe.evidence_field.value == "location"


def test_us_pronoun_is_not_a_region_match() -> None:
    evidence = extract_geography(
        "Join us and help customers everywhere succeed.",
        location_text=None,
        is_remote=None,
    )
    assert all(item.dimension != "region" for item in evidence)


def test_anywhere_guarded_against_scoped_place() -> None:
    scoped = extract_geography(
        "Work anywhere in the United States.",
        location_text=None,
        is_remote=True,
    )
    assert not any(item.geography_code == "region_worldwide" for item in scoped)
    assert any(item.geography_code == "region_north_america" for item in scoped)

    unscoped = extract_geography(
        "Work from anywhere.",
        location_text=None,
        is_remote=True,
    )
    assert any(item.geography_code == "region_worldwide" for item in unscoped)


def test_empty_inputs_yield_no_evidence() -> None:
    assert extract_geography(None, location_text=None, is_remote=None) == ()
    assert extract_geography("", location_text="", is_remote=None) == ()


def test_repeated_calls_deterministic_and_sorted_by_code() -> None:
    first = extract_geography(
        "Worldwide remote team with EU and APAC entities.",
        location_text="Global",
        is_remote=True,
    )
    second = extract_geography(
        "Worldwide remote team with EU and APAC entities.",
        location_text="Global",
        is_remote=True,
    )
    assert first == second
    codes = [item.geography_code for item in first]
    assert codes == sorted(codes)
