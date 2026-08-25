"""Versioned deterministic role taxonomy and pure title-first extraction."""

import re
from dataclasses import dataclass
from enum import StrEnum

ROLE_TAXONOMY_VERSION = "3"


class RoleEvidenceField(StrEnum):
    """Normalized posting field that supplied role evidence."""

    TITLE = "title"
    DESCRIPTION = "description"


class RoleMatchKind(StrEnum):
    """How a deterministic role rule accepted its evidence."""

    TITLE_PATTERN = "title_pattern"
    DESCRIPTION_STATEMENT = "description_statement"


@dataclass(frozen=True, slots=True)
class RoleEvidence:
    """One immutable direct functional-role classification with evidence."""

    role_code: str
    role_name: str
    evidence_field: RoleEvidenceField
    matched_text: str
    evidence_text: str
    rule_id: str
    match_kind: RoleMatchKind


@dataclass(frozen=True, slots=True)
class RoleRule:
    """One stable regex rule for a direct functional-role phrase."""

    rule_id: str
    pattern: str
    priority: int = 100


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    """One language-neutral role code and its versioned English-oriented rules."""

    code: str
    name: str
    rules: tuple[RoleRule, ...]


def _rule(rule_id: str, pattern: str, *, priority: int = 100) -> RoleRule:
    return RoleRule(rule_id=rule_id, pattern=pattern, priority=priority)


ROLE_TAXONOMY: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        "ai_ml",
        "AI / ML",
        (
            _rule(
                "ai_ml.engineer",
                r"\b(?:ai|ml|artificial\s+intelligence|machine\s+learning)\s+"
                r"(?:(?:research|platform)\s+)?(?:engineer|developer|specialist)\b",
            ),
            _rule(
                "ai_ml.research_engineer",
                r"\bai\s+research\s+engineer\b",
                priority=90,
            ),
            _rule("ai_ml.applied_scientist", r"\bapplied\s+scientist\b"),
            _rule("ai_ml.product_engineer", r"\bai\s+product\s+engineer\b"),
        ),
    ),
    RoleDefinition(
        "backend",
        "Backend",
        (
            _rule(
                "backend.engineer",
                r"\b(?:back[\s-]?end|server[\s-]?side)\s+"
                r"(?:software\s+)?(?:engineer|developer)\b",
            ),
            _rule("backend.oriented", r"\bback[\s-]?end\s+oriented\b"),
            _rule(
                "backend.engineer_suffix",
                r"\b(?:software\s+)?(?:engineer|developer)\s*[-,/|]\s*back[\s-]?end\b",
            ),
            _rule(
                "backend.platform_compound",
                r"\bback[\s-]?end\s*(?:/|\||[-–—])\s*platform\s+engineer\b",
            ),
            _rule(
                "backend.parenthetical_suffix",
                r"\b(?:software\s+)?(?:engineer|developer)\s*"
                r"\(\s*back[\s-]?end\s*\)",
            ),
        ),
    ),
    RoleDefinition(
        "blockchain_protocol",
        "Blockchain / Protocol",
        (
            _rule(
                "blockchain_protocol.solidity",
                r"\bsolidity\s+(?:protocol\s+)?(?:engineer|developer)\b",
                priority=80,
            ),
            _rule(
                "blockchain_protocol.smart_contract",
                r"\bsmart[\s-]+contract\s+(?:software\s+)?(?:engineer|developer)\b",
            ),
            _rule(
                "blockchain_protocol.blockchain",
                r"\b(?:blockchain|on[\s-]?chain)\s+"
                r"(?:protocol\s+)?(?:software\s+)?(?:engineer|developer)\b",
            ),
            _rule(
                "blockchain_protocol.protocol",
                r"\b(?:blockchain|web3|solidity|evm)\s+protocol\s+engineer\b",
            ),
        ),
    ),
    RoleDefinition(
        "community",
        "Community",
        (
            _rule("community.manager", r"\bcommunity\s+(?:manager|lead)\b"),
            _rule(
                "community.developer_relations",
                r"\b(?:developer\s+(?:relations|advocate)|devrel)\b",
            ),
        ),
    ),
    RoleDefinition(
        "data",
        "Data",
        (
            _rule(
                "data.engineer",
                r"\b(?:blockchain\s+)?data\s+(?:platform\s+)?engineer\b",
            ),
            _rule(
                "data.engineer_suffix",
                r"\bsoftware\s+engineer\s*[-,/|]\s*data\b",
            ),
            _rule(
                "data.analytics",
                r"\b(?:analytics\s+engineer|data\s+(?:scientist|analyst))\b",
            ),
        ),
    ),
    RoleDefinition(
        "delivery_engineering",
        "Delivery / Forward-Deployed Engineering",
        (
            _rule(
                "delivery_engineering.forward_deployed",
                r"\bforward[\s-]+deployed\s+(?:software\s+)?engineer(?:ing)?\b",
            ),
            _rule(
                "delivery_engineering.deployment_strategist",
                r"\bdeployment\s+strategist\b",
                priority=90,
            ),
            _rule(
                "delivery_engineering.implementation_consultant",
                r"\bimplementation\s+consultant\b",
                priority=90,
            ),
            _rule(
                "delivery_engineering.professional_services",
                r"\bprofessional\s+services\s+consultant\b",
                priority=90,
            ),
        ),
    ),
    RoleDefinition(
        "design",
        "Design",
        (
            _rule(
                "design.product",
                r"\bproduct\s+(?:designer|design\s+lead)\b",
            ),
            _rule(
                "design.ux_ui",
                r"\b(?:(?:ui|ux|ui\s*/\s*ux|ux\s*/\s*ui)\s+designer|"
                r"user\s+experience\s+designer)\b",
            ),
            _rule(
                "design.visual",
                r"\b(?:brand|graphic|motion|visual)\s+designer\b",
            ),
        ),
    ),
    RoleDefinition(
        "devops_platform",
        "DevOps / Platform",
        (
            _rule(
                "devops_platform.devops",
                r"\bdev[\s-]?ops\s+(?:engineer|developer|lead)\b",
            ),
            _rule(
                "devops_platform.platform",
                r"\b(?:data\s+|machine\s+learning\s+)?platform\s+engineer\b",
            ),
            _rule(
                "devops_platform.developer_platform",
                r"\bsoftware\s+engineer\s*,\s*developer\s+platform\b",
            ),
            _rule(
                "devops_platform.sre",
                r"\b(?:site\s+reliability\s+engineer|"
                r"database\s+reliability\s+engineer|sre)\b",
            ),
            _rule(
                "devops_platform.infrastructure",
                r"\b(?:infrastructure|systems?)\s+(?:operations\s+)?engineer\b",
            ),
            _rule(
                "devops_platform.infrastructure_suffix",
                r"\bsecurity\s+engineer\s*(?:/|\||[-–—,])\s*infrastructure\b",
            ),
            _rule(
                "devops_platform.gitops",
                r"\bgit[\s-]?ops\s+(?:engineer|lead)\b",
            ),
            _rule(
                "devops_platform.cloud",
                r"\bcloud\s+(?:infrastructure\s+)?engineer\b",
            ),
            _rule(
                "devops_platform.site_reliability_compound",
                r"\bsite\s+reliability\b[^.;]{0,40}?\bengineer\b",
            ),
        ),
    ),
    RoleDefinition(
        "finance",
        "Finance",
        (
            _rule(
                "finance.named",
                r"\b(?:financial\s+analyst|accountant|controller|portfolio\s+manager|"
                r"(?:crypto|foreign\s+exchange|fx)?\s*trader|tax\s+associate|"
                r"billing\s+officer|finance\s+manager|quant\s+(?:developer|researcher)|"
                r"crypto\s+market\s+specialist)\b",
            ),
            _rule(
                "finance.leadership",
                r"\b(?:head|vp|svp|director)\s+of\s+finance\b",
            ),
            _rule(
                "finance.market_strategy",
                r"\bhead\s+of\s+crypto\s+market\s+strategy\b",
            ),
            _rule(
                "finance.trust",
                r"\btrust\s+(?:officer|administrator|accounting\s+analyst)\b|"
                r"\bdirector\s+of\s+trust\s+administration\b",
            ),
            _rule(
                "finance.revenue_accounting",
                r"\brevenue\s+accounting\s+(?:manager|analyst|specialist|"
                r"associate)|\brevenue\s+accountant\b",
            ),
        ),
    ),
    RoleDefinition(
        "frontend",
        "Frontend",
        (
            _rule(
                "frontend.engineer",
                r"\bfront[\s-]?end\s+(?:software\s+)?(?:engineer|developer)\b",
            ),
            _rule("frontend.ui_engineer", r"\bui\s+engineer\b"),
        ),
    ),
    RoleDefinition(
        "full_stack",
        "Full Stack",
        (
            _rule(
                "full_stack.engineer",
                r"\bfull[\s-]?stack\s+(?:(?:software|ai)\s+)?"
                r"(?:engineer|developer)\b",
            ),
        ),
    ),
    RoleDefinition(
        "legal_compliance",
        "Legal / Compliance",
        (
            _rule(
                "legal_compliance.counsel",
                r"\b(?:legal|corporate|product|general|commercial)\s+counsel\b",
            ),
            _rule(
                "legal_compliance.compliance",
                r"\b(?:compliance\s+(?:officer|manager|analyst|lead)|"
                r"(?:head|director)\s+of\s+compliance)\b",
            ),
            _rule(
                "legal_compliance.aml",
                r"\baml\s+(?:analyst|officer|specialist)\b",
            ),
        ),
    ),
    RoleDefinition(
        "marketing_growth",
        "Marketing / Growth / Communications",
        (
            _rule(
                "marketing_growth.marketing",
                r"\b(?:(?:growth|product|content|lifecycle)\s+)?marketing\s+"
                r"(?:manager|lead|specialist|director)\b",
            ),
            _rule(
                "marketing_growth.leadership",
                r"\bhead\s+of\s+marketing\b",
            ),
            _rule(
                "marketing_growth.social_media",
                r"\bsocial\s+media(?:\s+and\s+community)?\s+"
                r"(?:manager|lead|specialist)\b",
            ),
            _rule(
                "marketing_growth.communications",
                r"\b(?:pr\s*(?:&|and)\s*communications|communications)\s+"
                r"(?:associate|manager|lead|specialist)\b",
            ),
            _rule("marketing_growth.growth_marketer", r"\bgrowth\s+marketer\b"),
            _rule("marketing_growth.marketer", r"\bmarketer\b"),
            _rule(
                "marketing_growth.marketing_bd_operations",
                r"\bmarketing\s+bd\s+operations\b",
            ),
            _rule(
                "marketing_growth.events",
                r"\bevents?\s+(?:manager|lead|coordinator|specialist)\b",
            ),
        ),
    ),
    RoleDefinition(
        "mobile",
        "Mobile",
        (
            _rule(
                "mobile.named",
                r"\b(?:mobile|ios|android|react\s+native)\s+"
                r"(?:software\s+)?(?:engineer|developer)\b",
            ),
            _rule(
                "mobile.engineer_suffix",
                r"\bsoftware\s+engineer(?:\s+[ivx]+)?\s*[-,/|]?\s+mobile\b",
            ),
        ),
    ),
    RoleDefinition(
        "operations",
        "Operations",
        (
            _rule("operations.coo", r"\bchief\s+operating\s+officer\b"),
            _rule(
                "operations.manager",
                r"(?<!product\s)(?<!marketing\s)(?<!sales\s)(?<!finance\s)"
                r"(?<!people\s)(?<!revenue\s)(?<!security\s)(?<!developer\s)"
                r"\boperations\s+(?:manager|lead|director)\b",
            ),
            _rule(
                "operations.leadership",
                r"\b(?:director|head|vp|svp|manager)\s+(?:of\s+)?"
                r"(?:business\s+)?operations\b",
            ),
            _rule("operations.business", r"\bbusiness\s+operations\b"),
            _rule(
                "operations.named",
                r"\b(?:linkedin|support|marketing\s+bd)\s+operations\b",
            ),
            _rule(
                "operations.specialist",
                r"(?<!product\s)(?<!marketing\s)(?<!sales\s)(?<!finance\s)"
                r"(?<!people\s)(?<!revenue\s)(?<!security\s)(?<!developer\s)"
                r"(?<!support\s)(?<!customer\s)(?<!cloud\s)(?<!platform\s)"
                r"(?<!technical\s)(?<!service\s)"
                r"\boperations\s+(?:specialist|analyst|coordinator|associate)\b",
            ),
            _rule(
                "operations.assistants",
                r"\b(?:executive|administrative)\s+assistant\b",
            ),
        ),
    ),
    RoleDefinition(
        "product",
        "Product",
        (
            _rule(
                "product.management",
                r"\bproduct\s+(?:manager|owner|lead)\b",
            ),
        ),
    ),
    RoleDefinition(
        "qa",
        "QA",
        (
            _rule(
                "qa.named",
                r"\b(?:qa\s+(?:engineer|tester|analyst)|quality\s+assurance\s+"
                r"(?:engineer|tester|analyst)|test\s+automation\s+engineer)\b",
            ),
        ),
    ),
    RoleDefinition(
        "sales_bd",
        "Sales / Business Development",
        (
            _rule(
                "sales_bd.sales",
                r"\b(?:technical\s+)?sales\s+"
                r"(?:manager|director|lead|executive|engineer)\b",
            ),
            _rule(
                "sales_bd.business_development",
                r"\bbusiness\s+development(?:\s+(?:manager|associate|lead|director))?\b",
            ),
            _rule(
                "sales_bd.bd",
                r"(?<!\w)bd(?:\s+(?:assistant|manager|lead|operations))?(?!\w)",
            ),
            _rule(
                "sales_bd.accounts",
                r"\b(?:strategic\s+account\s+executive|head\s+of\s+strategic\s+accounts)\b",
            ),
            _rule(
                "sales_bd.partnerships",
                r"\bpartnerships?\s+(?:manager|lead|director|associate|"
                r"specialist)\b",
            ),
            _rule(
                "sales_bd.solutions",
                r"\b(?:head\s+of\s+)?solutions\s+engineer(?:ing)?\b",
            ),
            _rule(
                "sales_bd.account",
                r"\b(?:enterprise|strategic|commercial|mid[\s-]?market|major)?\s*"
                r"account\s+(?:executive|manager)\b",
            ),
            _rule(
                "sales_bd.representative",
                r"\bsales\s+(?:development\s+representative|representative|"
                r"associate|specialist|consultant)\b",
            ),
            _rule(
                "sales_bd.sdr_bdr",
                r"(?<![\w-])(?:sdr|bdr)(?![\w-])",
                priority=90,
            ),
            _rule(
                "sales_bd.alliances",
                r"\b(?:alliances?\s+(?:manager|lead|director)|"
                r"head\s+of\s+[\w\s]{0,30}alliances?)\b",
            ),
            _rule(
                "sales_bd.leadership",
                r"\b(?:head|vp|svp|director)\s+of\s+sales\b",
            ),
            _rule(
                "sales_bd.sales_development_leadership",
                r"\b(?:manager|director|lead),?\s+sales\s+development\b|"
                r"\bsales\s+development\s+(?:manager|director|lead)\b",
            ),
            _rule(
                "sales_bd.deal_operations",
                r"\bdeal\s+(?:desk|operations)\b|"
                r"\bsales\s+operations\s+(?:analyst|specialist|administrator|"
                r"manager)\b",
            ),
        ),
    ),
    RoleDefinition(
        "security",
        "Security",
        (
            _rule(
                "security.engineer",
                r"\b(?:application\s+|it\s+|cyber\s*)?security\s+"
                r"(?:engineer|researcher|analyst)\b",
            ),
            _rule(
                "security.researcher",
                r"\bsecurity\s+researcher\b",
            ),
            _rule(
                "security.cybersecurity",
                r"\bcybersecurity\s+(?:engineer|analyst|specialist)\b",
            ),
            _rule(
                "security.operations",
                r"\bsecurity\s+operations\s+(?:analyst|engineer|specialist)\b",
            ),
            _rule(
                "security.soc",
                r"\bsoc\s+(?:analyst|engineer|manager)\b",
            ),
            _rule(
                "security.specialist",
                r"\bsecurity\s+(?:specialist|architect|consultant|manager)\b",
            ),
        ),
    ),
    RoleDefinition(
        "solutions_architect",
        "Solutions Architecture",
        (
            _rule(
                "solutions_architect.named",
                r"\b(?:delivery\s+|senior\s+|sr\.?\s+|staff\s+|principal\s+|"
                r"lead\s+|cloud\s+|data\s+|technical\s+)?solutions?\s+"
                r"architect\b",
            ),
            _rule(
                "solutions_architect.inverted",
                r"\barchitect\s*,\s*solutions?\b",
                priority=90,
            ),
        ),
    ),
    RoleDefinition(
        "support",
        "Support / Trust & Safety",
        (
            _rule(
                "support.customer",
                r"\bcustomer\s+(?:support|service)\s+(?:agent|representative|"
                r"specialist|engineer|manager)\b",
            ),
            _rule(
                "support.technical",
                r"\btechnical\s+support\s+(?:engineer|specialist|agent)\b",
            ),
            _rule("support.operations", r"\bsupport\s+operations\b"),
            _rule(
                "support.trust_safety",
                r"\btrust\s*(?:&|&amp;|and)\s*safety"
                r"(?:\s+(?:operations|ops|lead|manager))?\b",
            ),
            _rule(
                "support.engineer",
                r"\bsupport\s+engineer\b",
            ),
            _rule(
                "support.customer_success",
                r"\bcustomer\s+success\s+(?:manager|specialist|lead|"
                r"representative|associate)\b",
            ),
        ),
    ),
)

ROLE_CODES: tuple[str, ...] = tuple(role.code for role in ROLE_TAXONOMY)


@dataclass(frozen=True, slots=True)
class _CompiledRule:
    role_code: str
    role_name: str
    rule: RoleRule
    pattern: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class _Candidate:
    evidence: RoleEvidence
    priority: int
    start: int
    matched_length: int

    def selection_key(self) -> tuple[int, int, int, str]:
        return (
            self.priority,
            self.start,
            -self.matched_length,
            self.evidence.rule_id,
        )


_COMPILED_RULES = tuple(
    _CompiledRule(
        role_code=role.code,
        role_name=role.name,
        rule=rule,
        pattern=re.compile(rule.pattern, re.IGNORECASE),
    )
    for role in ROLE_TAXONOMY
    for rule in role.rules
)

_RELATIONSHIP_CONTEXT = re.compile(
    r"(?:work(?:ing)?|collaborat(?:e|ing)|partner(?:ing)?|coordinate|support(?:ing)?)"
    r"\s+(?:closely\s+)?(?:with\s+)?(?:our|the|a|an)?\s*$",
    re.IGNORECASE,
)
_ROLE_STATEMENT_CONTEXT = re.compile(
    r"(?:looking\s+for|hiring|seeking|join(?:ing)?(?:\s+\w+){0,5}\s+as|"
    r"this\s+(?:role|position)\s+is\s+for|the\s+role\s+is|"
    r"you\s+(?:are|will\s+serve\s+as))"
    r"(?:\s+(?:a|an))?"
    r"(?:\s+(?:talented|experienced|seasoned|skilled|senior|junior|staff|"
    r"principal|remote)){0,3}$",
    re.IGNORECASE,
)
_NEGATED_ROLE_STATEMENT_CONTEXT = re.compile(
    r"(?:not|no\s+longer)\s+(?:currently\s+)?"
    r"(?:looking\s+for|hiring|seeking)"
    r"(?:\s+(?:a|an))?"
    r"(?:\s+(?:talented|experienced|seasoned|skilled|senior|junior|staff|"
    r"principal|remote)){0,3}$",
    re.IGNORECASE,
)
_HEADER_PREFIX = re.compile(
    r"^\s*(?:(?:job\s+title|position|role)\s*[:\-]\s*)?"
    r"(?:(?:remote|entry[\s-]level|junior|mid|senior|sr\.?|staff|principal|"
    r"lead|head|founding)\s+)*$",
    re.IGNORECASE,
)
_MAX_EVIDENCE_SNIPPET_LENGTH = 120


def extract_roles(
    title: str,
    description_text: str | None,
) -> tuple[RoleEvidence, ...]:
    """Return direct role evidence using title first and conservative fallback."""

    title_candidates = _extract_candidates(
        title,
        evidence_field=RoleEvidenceField.TITLE,
        match_kind=RoleMatchKind.TITLE_PATTERN,
        require_description_context=False,
    )
    selected = _select_one_per_role(title_candidates)
    if selected:
        return _ordered_evidence(selected)

    if description_text is None or not description_text.strip():
        return ()

    description_candidates = _extract_candidates(
        description_text,
        evidence_field=RoleEvidenceField.DESCRIPTION,
        match_kind=RoleMatchKind.DESCRIPTION_STATEMENT,
        require_description_context=True,
    )
    return _ordered_evidence(_select_one_per_role(description_candidates))


def _extract_candidates(
    text: str,
    *,
    evidence_field: RoleEvidenceField,
    match_kind: RoleMatchKind,
    require_description_context: bool,
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for compiled in _COMPILED_RULES:
        for match in compiled.pattern.finditer(text):
            if require_description_context and not _is_role_statement(text, match):
                continue
            candidates.append(
                _Candidate(
                    evidence=RoleEvidence(
                        role_code=compiled.role_code,
                        role_name=compiled.role_name,
                        evidence_field=evidence_field,
                        matched_text=_collapse_whitespace(match.group(0)),
                        evidence_text=_evidence_snippet(
                            text,
                            match.start(),
                            match.end(),
                        ),
                        rule_id=compiled.rule.rule_id,
                        match_kind=match_kind,
                    ),
                    priority=compiled.rule.priority,
                    start=match.start(),
                    matched_length=match.end() - match.start(),
                )
            )
    return candidates


def _is_role_statement(text: str, match: re.Match[str]) -> bool:
    before = text[max(0, match.start() - 140) : match.start()]
    collapsed_before = _collapse_whitespace(before)
    if _RELATIONSHIP_CONTEXT.search(collapsed_before):
        return False
    if _NEGATED_ROLE_STATEMENT_CONTEXT.search(collapsed_before):
        return False
    if _ROLE_STATEMENT_CONTEXT.search(collapsed_before):
        return True
    return match.start() <= 100 and bool(_HEADER_PREFIX.fullmatch(text[: match.start()]))


def _select_one_per_role(candidates: list[_Candidate]) -> dict[str, _Candidate]:
    selected: dict[str, _Candidate] = {}
    for candidate in candidates:
        current = selected.get(candidate.evidence.role_code)
        if current is None or candidate.selection_key() < current.selection_key():
            selected[candidate.evidence.role_code] = candidate
    return selected


def _ordered_evidence(selected: dict[str, _Candidate]) -> tuple[RoleEvidence, ...]:
    return tuple(selected[code].evidence for code in sorted(selected))


def _evidence_snippet(text: str, start: int, end: int) -> str:
    max_context = 55
    left = max(0, start - max_context)
    right = min(len(text), end + max_context)

    if left > 0:
        whitespace = next(
            (index for index in range(left, start) if text[index].isspace()),
            None,
        )
        if whitespace is not None:
            left = whitespace + 1
    if right < len(text):
        whitespace = next(
            (index for index in range(right - 1, end - 1, -1) if text[index].isspace()),
            None,
        )
        if whitespace is not None:
            right = whitespace

    snippet = _collapse_whitespace(text[left:right])
    if left > 0:
        snippet = f"…{snippet}"
    if right < len(text):
        snippet = f"{snippet}…"
    if len(snippet) > _MAX_EVIDENCE_SNIPPET_LENGTH:
        snippet = f"{snippet[: _MAX_EVIDENCE_SNIPPET_LENGTH - 1].rstrip()}…"
    return snippet


def _collapse_whitespace(value: str) -> str:
    collapsed = " ".join(value.split())
    return "".join(
        character if character.isprintable() else "�" for character in collapsed
    )
