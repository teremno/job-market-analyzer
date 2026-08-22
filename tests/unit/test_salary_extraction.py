import pytest

from job_market_analyzer.intelligence.salaries import (
    SALARY_TAXONOMY_VERSION,
    extract_salary_estimate,
)


def test_taxonomy_version_is_v1() -> None:
    assert SALARY_TAXONOMY_VERSION == "1"


def test_structured_yearly_passes_through_directly() -> None:
    estimate = extract_salary_estimate(
        None,
        salary_min="90000",
        salary_max="110000",
        salary_currency="USD",
        salary_period="yearly",
    )[0]

    assert estimate.provenance == "structured"
    assert estimate.confidence == "direct"
    assert estimate.min_value == "90000"
    assert estimate.max_value == "110000"
    assert estimate.currency == "USD"
    assert estimate.annual_min == "90000"
    assert estimate.annual_max == "110000"
    assert estimate.annualized is False


def test_structured_monthly_is_derived_annually() -> None:
    estimate = extract_salary_estimate(
        None,
        salary_min="5000",
        salary_max=None,
        salary_currency="EUR",
        salary_period="monthly",
    )[0]

    assert estimate.period == "monthly"
    assert estimate.annualized is True
    assert estimate.annual_min == "60000"
    assert estimate.min_value == "5000"


def test_text_range_with_explicit_year() -> None:
    estimate = extract_salary_estimate("$90,000 - $110,000 a year")[0]

    assert estimate.provenance == "text"
    assert estimate.min_value == "90000"
    assert estimate.max_value == "110000"
    assert estimate.currency == "USD"
    assert estimate.period == "yearly"
    assert estimate.annualized is False


def test_text_k_notation_and_hourly_annualization() -> None:
    estimate = extract_salary_estimate("€60k - €80k per year")[0]
    assert estimate.min_value == "60000"
    assert estimate.max_value == "80000"
    assert estimate.currency == "EUR"

    hourly = extract_salary_estimate("£45/hour")[0]
    assert hourly.period == "hourly"
    assert hourly.annualized is True
    assert hourly.annual_min == "93600"
    assert hourly.max_value == "45"


def test_up_to_sets_maximum_only() -> None:
    estimate = extract_salary_estimate("Up to $150k annually")[0]

    assert estimate.min_value is None
    assert estimate.max_value == "150000"
    assert estimate.annual_min is None


def test_unknown_period_stores_bounds_without_annual_guess() -> None:
    estimate = extract_salary_estimate("120000 - 140000 USD")[0]

    assert estimate.period is None
    assert estimate.annualized is False
    assert estimate.annual_min is None
    assert estimate.annual_max is None
    assert estimate.min_value == "120000"
    assert estimate.max_value == "140000"


def test_no_currency_does_not_invent_one() -> None:
    estimate = extract_salary_estimate("90,000 to 100,000 per year")[0]
    assert estimate.currency is None
    assert estimate.period == "yearly"


def test_equity_only_mentions_produce_no_estimate() -> None:
    assert extract_salary_estimate("Competitive salary plus equity tokens") == ()


def test_inverted_range_rejected() -> None:
    assert extract_salary_estimate(None, salary_min="150000", salary_max="90000") == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"salary_text": ""},
        {"salary_text": "   "},
    ],
)
def test_no_salary_data_yields_no_estimate(kwargs: dict[str, object]) -> None:
    assert extract_salary_estimate(kwargs.get("salary_text")) == ()
