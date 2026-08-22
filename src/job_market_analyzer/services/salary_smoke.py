"""Bounded one-shot salary intelligence over current durable postings."""

from dataclasses import dataclass
from decimal import Decimal

from job_market_analyzer.intelligence.repository import (
    SalaryIntelligenceRepository,
)
from job_market_analyzer.services.salary_analysis import analyze_job_salary
from job_market_analyzer.storage.repository import JobPostingReader


@dataclass(frozen=True, slots=True)
class CurrencyCount:
    """Distinct-posting count for one currency among salary estimates."""

    currency: str
    postings: int


@dataclass(frozen=True, slots=True)
class SalarySmokeSummary:
    """Aggregate result of one bounded manual salary execution."""

    postings_considered: int
    new_analysis_runs: int
    existing_analysis_runs_reused: int
    estimated_postings: int
    no_salary_postings: int
    structured_postings: int
    text_parsed_postings: int
    annualized_postings: int
    median_annual_min_by_currency: tuple[CurrencyCount, ...]
    currency_counts: tuple[CurrencyCount, ...]


def run_salary_smoke(
    posting_reader: JobPostingReader,
    intelligence_repository: SalaryIntelligenceRepository,
    *,
    limit: int,
) -> SalarySmokeSummary:
    """Analyze one deterministic current-posting scope without swallowing errors."""

    if limit < 1:
        raise ValueError("limit must be greater than zero")

    postings = posting_reader.list_job_postings(limit=limit)
    new_runs = 0
    reused_runs = 0
    estimated = 0
    no_salary = 0
    structured = 0
    text_parsed = 0
    annualized = 0
    annual_mins_by_currency: dict[str, list[Decimal]] = {}
    currency_counts: dict[str, int] = {}

    for posting in postings:
        result = analyze_job_salary(posting, intelligence_repository)
        if result.analysis_created:
            new_runs += 1
        else:
            reused_runs += 1

        estimate = intelligence_repository.get_salary_estimate(
            result.analysis_run_id
        )
        if estimate is None:
            no_salary += 1
            continue

        estimated += 1
        if estimate.provenance == "structured":
            structured += 1
        else:
            text_parsed += 1
        if estimate.annualized:
            annualized += 1

        if estimate.currency is not None:
            key = estimate.currency.upper()
            currency_counts[key] = currency_counts.get(key, 0) + 1
        if estimate.currency is not None and estimate.annual_min is not None:
            annual_mins_by_currency.setdefault(
                estimate.currency.upper(), []
            ).append(Decimal(estimate.annual_min))

    def _median(values: list[Decimal]) -> Decimal:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2

    medians = tuple(
        CurrencyCount(currency, int(_median(annual_mins_by_currency[currency])))
        for currency in sorted(annual_mins_by_currency)
        if annual_mins_by_currency[currency]
    )
    currencies = tuple(
        CurrencyCount(currency, count)
        for currency, count in sorted(
            currency_counts.items(), key=lambda item: (-item[1], item[0])
        )
    )
    return SalarySmokeSummary(
        postings_considered=len(postings),
        new_analysis_runs=new_runs,
        existing_analysis_runs_reused=reused_runs,
        estimated_postings=estimated,
        no_salary_postings=no_salary,
        structured_postings=structured,
        text_parsed_postings=text_parsed,
        annualized_postings=annualized,
        median_annual_min_by_currency=medians,
        currency_counts=currencies,
    )
