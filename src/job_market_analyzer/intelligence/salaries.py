"""Versioned deterministic salary normalization over posting salary inputs.

Salary v1 works on two provenance paths:

1. ``structured``: the posting already carries normalized ``salary_min`` /
   ``salary_max`` / ``salary_currency`` / ``salary_period`` (Himalayas, Jobicy).
   Values pass through untouched with ``direct`` confidence; annual equivalents
   are derived only when the period is known, using explicit standard
   conventions (2080 work hours, 260 work days, 52 weeks, 12 months).
2. ``text``: the posting exposes free-text salary (Remotive, Web3.career).
   The parser accepts common English-language formats, requires an unambiguous
   period before deriving annual figures, and never invents a currency.

When the period is unknown the estimate records parsed bounds with null annual
figures instead of guessing. Ranges where the minimum exceeds the maximum are
rejected entirely rather than silently swapped.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SALARY_TAXONOMY_VERSION = "1"

ANNUAL_FACTORS: dict[str, Decimal] = {
    "hourly": Decimal("2080"),
    "daily": Decimal("260"),
    "weekly": Decimal("52"),
    "monthly": Decimal("12"),
}

_SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}

_PERIOD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "hourly",
        re.compile(r"\b(?:an?\s+hour|per\s+hour|/?\s*h(?:r|ours?)\b|hourly)\b", re.I),
    ),
    ("daily", re.compile(r"\b(?:per\s+day|a\s+day|/?\s*days?\b|daily)\b", re.I)),
    ("weekly", re.compile(r"\b(?:per\s+week|a\s+week|/?\s*w(?:k|eeks?)\b|weekly)\b", re.I)),
    (
        "monthly",
        re.compile(
            r"\b(?:per\s+month|a\s+month|/?\s*mo(?:nth)?s?\b|monthly)\b", re.I
        ),
    ),
    (
        "yearly",
        re.compile(
            r"\b(?:per\s+(?:year|annum)|a\s+year|annual(?:ly)?|/?\s*y(?:ea)?r(?:ly)?\b)",
            re.I,
        ),
    ),
)

_AMOUNT_PATTERN = re.compile(
    r"(?P<currency>[A-Z]{3}|\$|€|£)?\s*"
    r"(?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<thousand>[kK])?(?![\d])"
)

_RANGE_SEPARATOR = re.compile(r"^\s*[-–—/]|^\s+to\b", re.IGNORECASE)
_UP_TO_PREFIX = re.compile(r"(?:up\s+to|upwards\s+of)\s*$", re.IGNORECASE)
_MAX_ONLY_PREFIX = re.compile(
    r"^(?:up\s+to|as\s+much\s+as|salary[:\s]*)?", re.IGNORECASE
)
_EQUITY_GUARD = re.compile(r"\bequity\b|\btokens\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SalaryEstimate:
    """One immutable salary normalization result with provenance."""

    provenance: str
    confidence: str
    min_value: str | None
    max_value: str | None
    currency: str | None
    period: str | None
    annual_min: str | None
    annual_max: str | None
    annualized: bool
    matched_text: str
    rule_id: str
    evidence_field: str


def extract_salary_estimate(
    salary_text: str | None,
    *,
    salary_min: object = None,
    salary_max: object = None,
    salary_currency: str | None = None,
    salary_period: str | None = None,
) -> tuple[SalaryEstimate, ...]:
    """Return at most one salary estimate built from trusted inputs."""

    if salary_min is not None or salary_max is not None:
        return _structured_estimate(
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            salary_period=salary_period,
        )
    if salary_text is not None and salary_text.strip():
        return _text_estimate(salary_text.strip())
    return ()


def _structured_estimate(
    *,
    salary_min: object,
    salary_max: object,
    salary_currency: str | None,
    salary_period: str | None,
) -> tuple[SalaryEstimate, ...]:
    try:
        minimum = Decimal(str(salary_min)) if salary_min is not None else None
        maximum = Decimal(str(salary_max)) if salary_max is not None else None
    except InvalidOperation:
        return ()
    if minimum is None and maximum is None:
        return ()
    if minimum is not None and maximum is not None and minimum > maximum:
        return ()
    period = _canonical_period(salary_period)
    annual_min, annual_max, annualized = _annual_pair(minimum, maximum, period)
    display_min = minimum if minimum is not None else maximum
    display_max = maximum if maximum is not None else minimum
    assert display_min is not None and display_max is not None
    return (
        SalaryEstimate(
            provenance="structured",
            confidence="direct",
            min_value=_decimal_string(display_min),
            max_value=_decimal_string(display_max),
            currency=salary_currency,
            period=period,
            annual_min=annual_min,
            annual_max=annual_max,
            annualized=annualized,
            matched_text=f"{display_min}-{display_max}",
            rule_id="salary.structured",
            evidence_field="normalized",
        ),
    )


def _text_estimate(text: str) -> tuple[SalaryEstimate, ...]:
    if _EQUITY_GUARD.search(text):
        return ()
    amounts = _collect_amounts(text)
    if not amounts:
        return ()

    minimum: Decimal | None = None
    maximum: Decimal | None = None
    if len(amounts) >= 2:
        first_end = amounts[0][1][1]
        second_start = amounts[1][1][0]
        if _RANGE_SEPARATOR.match(text[first_end:second_start]):
            minimum, maximum = amounts[0][0], amounts[1][0]
        else:
            # Multiple unrelated numbers without a range separator are too
            # ambiguous to interpret conservatively.
            return ()
    else:
        value, (start, _) = amounts[0]
        prefix = text[max(0, start - 12) : start]
        if _UP_TO_PREFIX.search(prefix):
            maximum = value
        else:
            minimum = maximum = value

    currency = _detect_currency(text)
    period = _detect_period(text)
    annual_min, annual_max, annualized = _annual_pair(minimum, maximum, period)
    return (
        SalaryEstimate(
            provenance="text",
            confidence="parsed",
            min_value=_decimal_string(minimum) if minimum is not None else None,
            max_value=_decimal_string(maximum) if maximum is not None else None,
            currency=currency,
            period=period,
            annual_min=annual_min,
            annual_max=annual_max,
            annualized=annualized,
            matched_text=text[:80],
            rule_id="salary.text_parsed",
            evidence_field="normalized",
        ),
    )


def _collect_amounts(text: str) -> list[tuple[Decimal, tuple[int, int]]]:
    results: list[tuple[Decimal, tuple[int, int]]] = []
    for match in _AMOUNT_PATTERN.finditer(text):
        raw_number = match.group("number").replace(",", "")
        try:
            value = Decimal(raw_number)
        except InvalidOperation:
            continue
        if value <= 0:
            continue
        if match.group("thousand"):
            value *= Decimal("1000")
        results.append((value, (match.start(), match.end())))
        if len(results) == 2:
            break
    return results


def _detect_currency(text: str) -> str | None:
    iso = re.search(r"\b([A-Z]{3})\b", text)
    if iso is not None and iso.group(1) in {
        "USD",
        "EUR",
        "GBP",
        "CAD",
        "AUD",
        "CHF",
        "SEK",
        "NOK",
        "PLN",
        "UAH",
    }:
        return iso.group(1)
    for index, character in enumerate(text):
        if character in _SYMBOL_CURRENCY:
            return _SYMBOL_CURRENCY[character]
    return None


def _detect_period(text: str) -> str | None:
    for period, pattern in _PERIOD_PATTERNS:
        if pattern.search(text):
            return period
    return None


def _canonical_period(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    aliases = {
        "year": "yearly",
        "years": "yearly",
        "yr": "yearly",
        "yearly": "yearly",
        "annual": "yearly",
        "annum": "yearly",
        "month": "monthly",
        "months": "monthly",
        "week": "weekly",
        "weeks": "weekly",
        "day": "daily",
        "days": "daily",
        "hour": "hourly",
        "hours": "hourly",
    }
    if normalized in ANNUAL_FACTORS or normalized == "yearly":
        return normalized
    return aliases.get(normalized)


def _annual_pair(
    minimum: Decimal | None,
    maximum: Decimal | None,
    period: str | None,
) -> tuple[str | None, str | None, bool]:
    if period == "yearly":
        return (
            _decimal_string(minimum),
            _decimal_string(maximum),
            False,
        )
    factor = ANNUAL_FACTORS.get(period or "")
    if factor is None:
        # Without a known period the bounds are not claimed to be annual.
        return (None, None, False)
    annual_min = minimum * factor if minimum is not None else None
    annual_max = maximum * factor if maximum is not None else None
    return (_decimal_string(annual_min), _decimal_string(annual_max), True)


def _decimal_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    quantized = value.quantize(Decimal("0.01"))
    formatted = format(quantized, "f").rstrip("0").rstrip(".")
    return formatted or "0"
