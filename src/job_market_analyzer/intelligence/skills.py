"""Versioned skill taxonomy and pure deterministic extraction rules."""

import re
from dataclasses import dataclass
from enum import StrEnum

from job_market_analyzer.intelligence.models import (
    EvidenceField,
    MatchKind,
    SkillEvidence,
)

SKILL_TAXONOMY_VERSION = "5"


class ContextRule(StrEnum):
    """Named guard for aliases that are unsafe without technical context."""

    GO_LANGUAGE = "go_language"
    C_LANGUAGE = "c_language"
    REACT_FRAMEWORK = "react_framework"
    RUST_LANGUAGE = "rust_language"
    FOUNDRY_WEB3 = "foundry_web3"
    ANGULAR_FRAMEWORK = "angular_framework"
    AZURE_CLOUD = "azure_cloud"
    FLASK_FRAMEWORK = "flask_framework"
    HARDHAT_WEB3 = "hardhat_web3"
    JAVA_LANGUAGE = "java_language"
    VUE_FRAMEWORK = "vue_framework"
    KAFKA_STREAMING = "kafka_streaming"
    PROMETHEUS_MONITORING = "prometheus_monitoring"
    SNOWFLAKE_DATA = "snowflake_data"
    COSMOS_BLOCKCHAIN = "cosmos_blockchain"
    FIGMA_DESIGN = "figma_design"
    SOLANA_TECHNICAL = "solana_technical"
    BASH_SHELL = "bash_shell"
    EXCEL_SPREADSHEET = "excel_spreadsheet"
    SPARK_DATA = "spark_data"
    POSITIONING_MARKETING = "positioning_marketing"
    AIRFLOW_INFRA = "airflow_infra"


@dataclass(frozen=True, slots=True)
class SkillAlias:
    """One stable alias-matching rule within a canonical skill."""

    rule_id: str
    alias: str
    match_kind: MatchKind = MatchKind.EXACT_ALIAS
    case_sensitive: bool = False
    context_rule: ContextRule | None = None


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    """One analyzer-curated canonical skill and its accepted aliases."""

    code: str
    name: str
    aliases: tuple[SkillAlias, ...]


def _exact(rule_id: str, alias: str, *, case_sensitive: bool = False) -> SkillAlias:
    return SkillAlias(
        rule_id=rule_id,
        alias=alias,
        case_sensitive=case_sensitive,
    )


def _contextual(
    rule_id: str,
    alias: str,
    context_rule: ContextRule,
    *,
    case_sensitive: bool = False,
) -> SkillAlias:
    return SkillAlias(
        rule_id=rule_id,
        alias=alias,
        match_kind=MatchKind.CONTEXTUAL,
        case_sensitive=case_sensitive,
        context_rule=context_rule,
    )


SKILL_TAXONOMY: tuple[SkillDefinition, ...] = (
    SkillDefinition(
        "ab_testing",
        "A/B Testing",
        (
            _exact("ab_testing.slash", "A/B testing"),
            _exact("ab_testing.plain", "AB testing"),
            _exact("ab_testing.split", "Split testing"),
        ),
    ),
    SkillDefinition(
        "account_management",
        "Account Management",
        (_exact("account_management.named", "Account management"),),
    ),
    SkillDefinition(
        "airflow",
        "Airflow",
        (
            _exact("airflow.apache_airflow", "Apache Airflow"),
            _contextual("airflow.airflow", "Airflow", ContextRule.AIRFLOW_INFRA),
        ),
    ),
    SkillDefinition(
        "aml",
        "AML",
        (
            _exact("aml.acronym", "AML"),
            _exact("aml.full_name", "Anti-money laundering"),
        ),
    ),
    SkillDefinition(
        "angular",
        "Angular",
        (
            _exact("angular.angular_framework", "Angular framework"),
            _exact("angular.angularjs", "AngularJS"),
            _contextual(
                "angular.angular",
                "Angular",
                ContextRule.ANGULAR_FRAMEWORK,
            ),
        ),
    ),
    SkillDefinition(
        "aws",
        "AWS",
        (
            _exact("aws.amazon_web_services", "Amazon Web Services"),
            _exact("aws.aws", "AWS"),
        ),
    ),
    SkillDefinition(
        "azure",
        "Azure",
        (
            _exact("azure.microsoft_azure", "Microsoft Azure"),
            _contextual("azure.azure", "Azure", ContextRule.AZURE_CLOUD),
        ),
    ),
    SkillDefinition(
        "b2b_marketing",
        "B2B Marketing",
        (
            _exact("b2b_marketing.b2b_marketing", "B2B marketing"),
            _exact("b2b_marketing.b2b_saas_marketing", "B2B SaaS marketing"),
        ),
    ),
    SkillDefinition(
        "bash",
        "Bash",
        (
            _exact("bash.bash_shell", "Bash shell", case_sensitive=True),
            _contextual("bash.bash", "Bash", ContextRule.BASH_SHELL),
        ),
    ),
    SkillDefinition(
        "bigquery",
        "BigQuery",
        (_exact("bigquery.named", "BigQuery"),),
    ),
    SkillDefinition(
        "brand_marketing",
        "Brand Marketing",
        (
            _exact("brand_marketing.branding", "Branding"),
            _exact("brand_marketing.brand_marketing", "Brand marketing"),
            _exact("brand_marketing.brand_strategy", "Brand strategy"),
            _exact("brand_marketing.brand_management", "Brand management"),
        ),
    ),
    SkillDefinition(
        "budgeting",
        "Budgeting",
        (_exact("budgeting.named", "Budgeting"),),
    ),
    SkillDefinition("c", "C", (_contextual("c.c", "C", ContextRule.C_LANGUAGE, case_sensitive=True),)),
    SkillDefinition(
        "campaign_management",
        "Campaign Management",
        (
            _exact("campaign_management.management", "Campaign management"),
            _exact("campaign_management.campaigns_plural", "Marketing campaigns"),
            _exact("campaign_management.campaign_singular", "Marketing campaign"),
        ),
    ),
    SkillDefinition(
        "canva",
        "Canva",
        (_exact("canva.named", "Canva"),),
    ),
    SkillDefinition(
        "cicd",
        "CI/CD",
        (
            _exact("cicd.continuous_integration_delivery", "continuous integration and delivery"),
            _exact("cicd.continuous_integration_deployment", "continuous integration and deployment"),
            _exact("cicd.ci_slash_cd_spaced", "CI / CD"),
            _exact("cicd.ci_cd", "CI/CD"),
            _exact("cicd.cicd", "CICD"),
        ),
    ),
    SkillDefinition(
        "community_management",
        "Community Management",
        (_exact("community_management.named", "Community management"),),
    ),
    SkillDefinition(
        "content_marketing",
        "Content Marketing",
        (
            _exact("content_marketing.named", "Content marketing"),
            _exact("content_marketing.creation", "Content creation"),
            _exact("content_marketing.strategy", "Content strategy"),
        ),
    ),
    SkillDefinition(
        "copywriting",
        "Copywriting",
        (
            _exact("copywriting.named", "Copywriting"),
            _exact("copywriting.spaced", "Copy writing"),
        ),
    ),
    SkillDefinition(
        "cosmos",
        "Cosmos",
        (
            _exact("cosmos.cosmos_sdk", "Cosmos SDK"),
            _contextual(
                "cosmos.cosmos",
                "Cosmos",
                ContextRule.COSMOS_BLOCKCHAIN,
            ),
        ),
    ),
    SkillDefinition(
        "cpp",
        "C++",
        (
            _exact("cpp.c_plus_plus_words", "C plus plus"),
            _exact("cpp.cpp", "C++"),
        ),
    ),
    SkillDefinition(
        "crm",
        "CRM",
        (
            _exact("crm.acronym", "CRM"),
            _exact("crm.full_name", "Customer relationship management"),
            _exact("crm.hubspot", "HubSpot"),
        ),
    ),
    SkillDefinition(
        "csharp",
        "C#",
        (
            _exact("csharp.c_sharp", "C Sharp"),
            _exact("csharp.csharp", "C#"),
        ),
    ),
    SkillDefinition(
        "css",
        "CSS",
        (
            _exact("css.css3", "CSS3", case_sensitive=True),
            _exact("css.css", "CSS", case_sensitive=True),
        ),
    ),
    SkillDefinition(
        "customer_success",
        "Customer Success",
        (
            _exact("customer_success.named", "Customer success"),
            _exact("customer_success.manager", "Customer success manager"),
        ),
    ),
    SkillDefinition(
        "data_analysis",
        "Data Analysis",
        (_exact("data_analysis.named", "Data analysis"),),
    ),
    SkillDefinition(
        "data_modeling",
        "Data Modeling",
        (
            _exact("data_modeling.modeling", "Data modeling"),
            _exact("data_modeling.modelling", "Data modelling"),
        ),
    ),
    SkillDefinition(
        "dbt",
        "dbt",
        (_exact("dbt.named", "dbt", case_sensitive=True),),
    ),
    SkillDefinition(
        "deep_learning",
        "Deep Learning",
        (_exact("deep_learning.named", "Deep learning"),),
    ),
    SkillDefinition("defi", "DeFi", (_exact("defi.defi", "DeFi"), _exact("defi.decentralized_finance", "decentralized finance"))),
    SkillDefinition(
        "design_system",
        "Design Systems",
        (
            _exact("design_system.singular", "Design system"),
            _exact("design_system.plural", "Design systems"),
        ),
    ),
    SkillDefinition(
        "digital_marketing",
        "Digital Marketing",
        (_exact("digital_marketing.named", "Digital marketing"),),
    ),
    SkillDefinition("django", "Django", (_exact("django.django", "Django"),)),
    SkillDefinition("docker", "Docker", (_exact("docker.docker", "Docker"),)),
    SkillDefinition(
        "dotnet",
        ".NET",
        (
            _exact("dotnet.asp_dotnet", "ASP.NET"),
            _exact("dotnet.dotnet_word", "dotnet"),
            _exact("dotnet.dotnet", ".NET"),
        ),
    ),
    SkillDefinition(
        "enterprise_sales",
        "Enterprise Sales",
        (_exact("enterprise_sales.named", "Enterprise sales"),),
    ),
    SkillDefinition("ethereum", "Ethereum", (_exact("ethereum.ethereum", "Ethereum"),)),
    SkillDefinition(
        "ethersjs",
        "Ethers.js",
        (
            _exact("ethersjs.ethers_dot_js", "Ethers.js"),
            _exact("ethersjs.ethersjs", "EthersJS"),
        ),
    ),
    SkillDefinition(
        "etl",
        "ETL",
        (_exact("etl.acronym", "ETL"),),
    ),
    SkillDefinition(
        "evm",
        "EVM",
        (
            _exact("evm.ethereum_virtual_machine", "Ethereum Virtual Machine"),
            _exact("evm.evm", "EVM", case_sensitive=True),
        ),
    ),
    SkillDefinition(
        "excel",
        "Excel",
        (
            _exact("excel.microsoft_excel", "Microsoft Excel"),
            _contextual("excel.excel", "Excel", ContextRule.EXCEL_SPREADSHEET),
        ),
    ),
    SkillDefinition(
        "express",
        "Express",
        (
            _exact("express.express_dot_js", "Express.js"),
            _exact("express.expressjs", "ExpressJS"),
        ),
    ),
    SkillDefinition("fastapi", "FastAPI", (_exact("fastapi.fastapi", "FastAPI"),)),
    SkillDefinition(
        "figma",
        "Figma",
        (
            _exact("figma.figma_ai", "Figma AI"),
            _contextual(
                "figma.figma",
                "Figma",
                ContextRule.FIGMA_DESIGN,
            ),
        ),
    ),
    SkillDefinition(
        "financial_reporting",
        "Financial Reporting",
        (_exact("financial_reporting.named", "Financial reporting"),),
    ),
    SkillDefinition(
        "fine_tuning",
        "Fine-Tuning",
        (
            _exact("fine_tuning.hyphenated", "Fine-tuning"),
            _exact("fine_tuning.fine_tuning_spaced", "Fine tuning"),
            _exact("fine_tuning.model_fine_tuning", "Model fine-tuning"),
        ),
    ),
    SkillDefinition(
        "flask",
        "Flask",
        (
            _exact("flask.flask_framework", "Flask framework"),
            _contextual("flask.flask", "Flask", ContextRule.FLASK_FRAMEWORK),
        ),
    ),
    SkillDefinition(
        "forecasting",
        "Forecasting",
        (
            _exact("forecasting.bare", "Forecasting"),
            _exact("forecasting.sales", "Sales forecasting"),
            _exact("forecasting.financial", "Financial forecasting"),
        ),
    ),
    SkillDefinition(
        "foundry",
        "Foundry",
        (_contextual("foundry.foundry", "Foundry", ContextRule.FOUNDRY_WEB3),),
    ),
    SkillDefinition(
        "gcp",
        "Google Cloud",
        (
            _exact("gcp.google_cloud_platform", "Google Cloud Platform"),
            _exact("gcp.google_cloud", "Google Cloud"),
            _exact("gcp.gcp", "GCP"),
        ),
    ),
    SkillDefinition(
        "generative_ai",
        "Generative AI",
        (
            _exact("generative_ai.named", "Generative AI"),
            _exact("generative_ai.genai", "GenAI"),
        ),
    ),
    SkillDefinition("git", "Git", (_exact("git.git", "Git"),)),
    SkillDefinition(
        "github_actions",
        "GitHub Actions",
        (_exact("github_actions.github_actions", "GitHub Actions"),),
    ),
    SkillDefinition(
        "go",
        "Go",
        (
            _exact("go.golang", "Golang"),
            _contextual("go.go", "Go", ContextRule.GO_LANGUAGE),
        ),
    ),
    SkillDefinition(
        "go_to_market",
        "Go-to-Market",
        (
            _exact("go_to_market.hyphenated", "Go-to-market"),
            _exact("go_to_market.spaced", "Go to market"),
            _exact("go_to_market.gtm_strategy", "GTM strategy"),
        ),
    ),
    SkillDefinition(
        "google_ads",
        "Google Ads",
        (
            _exact("google_ads.named", "Google Ads"),
            _exact("google_ads.adwords", "Google AdWords"),
            _exact("google_ads.adwords_bare", "AdWords"),
        ),
    ),
    SkillDefinition(
        "google_analytics",
        "Google Analytics",
        (
            _exact("google_analytics.named", "Google Analytics"),
            _exact("google_analytics.ga4", "GA4"),
        ),
    ),
    SkillDefinition("grafana", "Grafana", (_exact("grafana.grafana", "Grafana"),)),
    SkillDefinition("graphql", "GraphQL", (_exact("graphql.graphql", "GraphQL"),)),
    SkillDefinition(
        "growth_marketing",
        "Growth Marketing",
        (
            _exact("growth_marketing.named", "Growth marketing"),
            _exact("growth_marketing.growth_lead", "Growth lead"),
        ),
    ),
    SkillDefinition(
        "hardhat",
        "Hardhat",
        (
            _exact("hardhat.hardhat_framework", "Hardhat framework"),
            _contextual("hardhat.hardhat", "Hardhat", ContextRule.HARDHAT_WEB3),
        ),
    ),
    SkillDefinition(
        "html",
        "HTML",
        (
            _exact("html.html5", "HTML5", case_sensitive=True),
            _exact("html.html", "HTML", case_sensitive=True),
        ),
    ),
    SkillDefinition(
        "incident_response",
        "Incident Response",
        (_exact("incident_response.named", "Incident response"),),
    ),
    SkillDefinition(
        "influencer_marketing",
        "Influencer Marketing",
        (
            _exact("influencer_marketing.named", "Influencer marketing"),
            _exact("influencer_marketing.influencers", "Influencers"),
        ),
    ),
    SkillDefinition(
        "java",
        "Java",
        (_contextual("java.java", "Java", ContextRule.JAVA_LANGUAGE),),
    ),
    SkillDefinition(
        "javascript",
        "JavaScript",
        (
            _exact("javascript.javascript", "JavaScript"),
            _exact("javascript.ecmascript", "ECMAScript"),
            _exact("javascript.js", "JS"),
        ),
    ),
    SkillDefinition(
        "kafka",
        "Apache Kafka",
        (
            _exact("kafka.apache_kafka", "Apache Kafka"),
            _exact("kafka.kafka_streams", "Kafka Streams"),
            _contextual(
                "kafka.kafka",
                "Kafka",
                ContextRule.KAFKA_STREAMING,
            ),
        ),
    ),
    SkillDefinition(
        "kubernetes",
        "Kubernetes",
        (
            _exact("kubernetes.kubernetes", "Kubernetes"),
            _exact("kubernetes.k8s", "K8s"),
        ),
    ),
    SkillDefinition(
        "lead_generation",
        "Lead Generation",
        (_exact("lead_generation.named", "Lead generation"),),
    ),
    SkillDefinition("linux", "Linux", (_exact("linux.linux", "Linux"),)),
    SkillDefinition(
        "llm",
        "LLM",
        (
            _exact("llm.acronym", "LLM"),
            _exact("llm.plural", "LLMs"),
            _exact("llm.full_name", "Large language model"),
        ),
    ),
    SkillDefinition(
        "machine_learning",
        "Machine Learning",
        (
            _exact("machine_learning.named", "Machine learning"),
            _exact(
                "machine_learning.ml_abbr",
                "ML",
                case_sensitive=True,
            ),
        ),
    ),
    SkillDefinition(
        "market_research",
        "Market Research",
        (_exact("market_research.named", "Market research"),),
    ),
    SkillDefinition(
        "marketing_analytics",
        "Marketing Analytics",
        (_exact("marketing_analytics.named", "Marketing analytics"),),
    ),
    SkillDefinition(
        "marketing_funnel",
        "Marketing Funnel",
        (
            _exact("marketing_funnel.funnel", "Funnel"),
            _exact("marketing_funnel.marketing_funnel", "Marketing funnel"),
            _exact("marketing_funnel.sales_funnel", "Sales funnel"),
            _exact("marketing_funnel.conversion_funnel", "Conversion funnel"),
            _exact("marketing_funnel.full_funnel", "Full-funnel"),
        ),
    ),
    SkillDefinition(
        "marketing_strategy",
        "Marketing Strategy",
        (_exact("marketing_strategy.named", "Marketing strategy"),),
    ),
    SkillDefinition("mongodb", "MongoDB", (_exact("mongodb.mongodb", "MongoDB"), _exact("mongodb.mongo", "Mongo"))),
    SkillDefinition("mysql", "MySQL", (_exact("mysql.mysql", "MySQL"),)),
    SkillDefinition(
        "negotiation",
        "Negotiation",
        (
            _exact("negotiation.singular", "Negotiation"),
            _exact("negotiation.plural", "Negotiations"),
        ),
    ),
    SkillDefinition(
        "nestjs",
        "NestJS",
        (
            _exact("nestjs.nest_dot_js", "Nest.js"),
            _exact("nestjs.nestjs", "NestJS"),
        ),
    ),
    SkillDefinition(
        "nextjs",
        "Next.js",
        (
            _exact("nextjs.next_dot_js", "Next.js"),
            _exact("nextjs.nextjs", "NextJS"),
        ),
    ),
    SkillDefinition(
        "nodejs",
        "Node.js",
        (
            _exact("nodejs.node_dot_js", "Node.js"),
            _exact("nodejs.nodejs", "NodeJS"),
            _exact("nodejs.node_js", "Node JS"),
        ),
    ),
    SkillDefinition(
        "owasp",
        "OWASP",
        (_exact("owasp.acronym", "OWASP"),),
    ),
    SkillDefinition(
        "paid_media",
        "Paid Media",
        (
            _exact("paid_media.named", "Paid media"),
            _exact("paid_media.paid_social", "Paid social"),
            _exact("paid_media.paid_search", "Paid search"),
            _exact("paid_media.ppc", "PPC"),
        ),
    ),
    SkillDefinition(
        "penetration_testing",
        "Penetration Testing",
        (
            _exact("penetration_testing.full", "Penetration testing"),
            _exact("penetration_testing.short", "Pen testing"),
        ),
    ),
    SkillDefinition(
        "performance_marketing",
        "Performance Marketing",
        (_exact("performance_marketing.named", "Performance marketing"),),
    ),
    SkillDefinition(
        "positioning",
        "Positioning",
        (
            _contextual(
                "positioning.positioning",
                "Positioning",
                ContextRule.POSITIONING_MARKETING,
            ),
        ),
    ),
    SkillDefinition(
        "postgresql",
        "PostgreSQL",
        (
            _exact("postgresql.postgresql", "PostgreSQL"),
            _exact("postgresql.postgres", "Postgres"),
        ),
    ),
    SkillDefinition(
        "product_design",
        "Product Design",
        (_exact("product_design.named", "Product design"),),
    ),
    SkillDefinition(
        "product_strategy",
        "Product Strategy",
        (_exact("product_strategy.named", "Product strategy"),),
    ),
    SkillDefinition(
        "prometheus",
        "Prometheus",
        (
            _exact("prometheus.prometheus_monitoring", "Prometheus monitoring"),
            _contextual(
                "prometheus.prometheus",
                "Prometheus",
                ContextRule.PROMETHEUS_MONITORING,
            ),
        ),
    ),
    SkillDefinition(
        "prompt_engineering",
        "Prompt Engineering",
        (_exact("prompt_engineering.named", "Prompt engineering"),),
    ),
    SkillDefinition(
        "prospecting",
        "Sales Prospecting",
        (
            _exact("prospecting.sales", "Sales prospecting"),
            _exact("prospecting.bare", "Prospecting"),
        ),
    ),
    SkillDefinition(
        "prototyping",
        "Prototyping",
        (
            _exact("prototyping.gerund", "Prototyping"),
            _exact("prototyping.noun", "Prototypes"),
        ),
    ),
    SkillDefinition(
        "public_relations",
        "Public Relations",
        (
            _exact("pr.full_name", "Public relations"),
            _exact("pr.pr_strategy", "PR strategy"),
        ),
    ),
    SkillDefinition("pytest", "pytest", (_exact("pytest.pytest", "pytest"), _exact("pytest.py_dot_test", "py.test"), _exact("pytest.py_test", "py test"))),
    SkillDefinition("python", "Python", (_exact("python.python", "Python"),)),
    SkillDefinition("pytorch", "PyTorch", (_exact("pytorch.pytorch", "PyTorch"),)),
    SkillDefinition(
        "react",
        "React",
        (
            _exact("react.react_dot_js", "React.js"),
            _exact("react.reactjs", "ReactJS"),
            _contextual("react.react", "React", ContextRule.REACT_FRAMEWORK),
        ),
    ),
    SkillDefinition(
        "react_native",
        "React Native",
        (_exact("react_native.react_native", "React Native"),),
    ),
    SkillDefinition("redis", "Redis", (_exact("redis.redis", "Redis"),)),
    SkillDefinition(
        "rest_api",
        "REST API",
        (
            _exact("rest_api.restful_apis", "RESTful APIs"),
            _exact("rest_api.restful_api", "RESTful API"),
            _exact("rest_api.rest_apis", "REST APIs"),
            _exact("rest_api.rest_api", "REST API"),
        ),
    ),
    SkillDefinition(
        "rust",
        "Rust",
        (_contextual("rust.rust", "Rust", ContextRule.RUST_LANGUAGE),),
    ),
    SkillDefinition(
        "sales_operations",
        "Sales Operations",
        (_exact("sales_operations.named", "Sales operations"),),
    ),
    SkillDefinition(
        "seo",
        "SEO",
        (
            _exact("seo.acronym", "SEO"),
            _exact("seo.full_name", "Search engine optimization"),
        ),
    ),
    SkillDefinition(
        "siem",
        "SIEM",
        (_exact("siem.acronym", "SIEM"),),
    ),
    SkillDefinition(
        "snowflake",
        "Snowflake",
        (
            _exact("snowflake.snowflake_data_cloud", "Snowflake Data Cloud"),
            _exact("snowflake.snowflake_warehouse", "Snowflake warehouse"),
            _contextual(
                "snowflake.snowflake",
                "Snowflake",
                ContextRule.SNOWFLAKE_DATA,
            ),
        ),
    ),
    SkillDefinition(
        "social_media_marketing",
        "Social Media Marketing",
        (
            _exact("smm.social_media", "Social media"),
            _exact("smm.marketing", "Social media marketing"),
            _exact("smm.management", "Social media management"),
        ),
    ),
    SkillDefinition(
        "solana",
        "Solana",
        (
            _exact("solana.solana_sdk", "Solana SDK"),
            _contextual(
                "solana.solana",
                "Solana",
                ContextRule.SOLANA_TECHNICAL,
            ),
        ),
    ),
    SkillDefinition("solidity", "Solidity", (_exact("solidity.solidity", "Solidity"),)),
    SkillDefinition(
        "spark",
        "Spark",
        (
            _exact("spark.apache_spark", "Apache Spark"),
            _contextual("spark.spark", "Spark", ContextRule.SPARK_DATA),
        ),
    ),
    SkillDefinition(
        "spring",
        "Spring",
        (
            _exact("spring.spring_framework", "Spring Framework"),
            _exact("spring.spring_boot", "Spring Boot"),
        ),
    ),
    SkillDefinition("sql", "SQL", (_exact("sql.sql", "SQL"),)),
    SkillDefinition("tensorflow", "TensorFlow", (_exact("tensorflow.tensorflow", "TensorFlow"),)),
    SkillDefinition("terraform", "Terraform", (_exact("terraform.terraform", "Terraform"),)),
    SkillDefinition(
        "troubleshooting",
        "Troubleshooting",
        (_exact("troubleshooting.named", "Troubleshooting"),),
    ),
    SkillDefinition("typescript", "TypeScript", (_exact("typescript.typescript", "TypeScript"),)),
    SkillDefinition(
        "user_research",
        "User Research",
        (_exact("user_research.named", "User research"),),
    ),
    SkillDefinition(
        "vue",
        "Vue",
        (
            _exact("vue.vue_dot_js", "Vue.js"),
            _exact("vue.vuejs", "VueJS"),
            _contextual("vue.vue", "Vue", ContextRule.VUE_FRAMEWORK),
        ),
    ),
    SkillDefinition(
        "vulnerability",
        "Vulnerability Management",
        (
            _exact("vulnerability.management", "Vulnerability management"),
            _exact("vulnerability.assessment", "Vulnerability assessment"),
            _exact("vulnerability.bare", "Vulnerabilities"),
        ),
    ),
    SkillDefinition(
        "web3js",
        "Web3.js",
        (
            _exact("web3js.web3_dot_js", "Web3.js"),
            _exact("web3js.web3js", "Web3JS"),
        ),
    ),
    SkillDefinition(
        "zendesk",
        "Zendesk",
        (_exact("zendesk.named", "Zendesk"),),
    ),

)


@dataclass(frozen=True, slots=True)
class _CompiledAlias:
    skill_code: str
    skill_name: str
    alias: SkillAlias
    pattern: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class _Candidate:
    evidence: SkillEvidence
    source_order: int
    start: int
    matched_length: int

    def selection_key(self) -> tuple[int, int, int, int, str]:
        match_priority = 0 if self.evidence.match_kind is MatchKind.EXACT_ALIAS else 1
        return (
            match_priority,
            self.source_order,
            self.start,
            -self.matched_length,
            self.evidence.rule_id,
        )


def _compile_alias(skill: SkillDefinition, alias: SkillAlias) -> _CompiledAlias:
    escaped_alias = re.escape(alias.alias).replace(r"\ ", r"\s+")
    prefix = r"(?<!\w)"
    suffix = r"(?!\w)"
    if alias.rule_id == "javascript.js":
        prefix = r"(?<![\w.])"
    elif alias.rule_id == "c.c":
        suffix = r"(?![\w+#])"
    elif alias.alias.endswith("++"):
        suffix = r"(?:(?=\d+(?!\w))|(?![\w+]))"
    elif alias.alias.endswith("#"):
        suffix = r"(?![\w#])"
    flags = 0 if alias.case_sensitive else re.IGNORECASE
    return _CompiledAlias(
        skill_code=skill.code,
        skill_name=skill.name,
        alias=alias,
        pattern=re.compile(rf"{prefix}{escaped_alias}{suffix}", flags),
    )


_COMPILED_ALIASES = tuple(
    _compile_alias(skill, alias)
    for skill in SKILL_TAXONOMY
    for alias in sorted(
        skill.aliases,
        key=lambda item: (-len(item.alias), item.rule_id),
    )
)

_FIELD_ORDER = {
    EvidenceField.TITLE: 0,
    EvidenceField.DESCRIPTION: 1,
    EvidenceField.TAG: 2,
}
_MAX_EVIDENCE_SNIPPET_LENGTH = 120

_RUST_NON_TECH = re.compile(
    r"\b(?:corrosion|corroded|metal|material|oxide|removal|resistant|surface)\b",
    re.IGNORECASE,
)


def extract_skills(
    title: str,
    description_text: str | None,
    source_tags: tuple[str, ...],
) -> tuple[SkillEvidence, ...]:
    """Extract deterministic taxonomy-backed skill mentions from one posting."""

    sources: list[tuple[EvidenceField, str, int]] = []
    if title:
        sources.append((EvidenceField.TITLE, title, 0))
    if description_text:
        sources.append((EvidenceField.DESCRIPTION, description_text, 0))
    for tag_index, tag in enumerate(
        sorted(set(source_tags), key=lambda value: (value.casefold(), value))
    ):
        if tag:
            sources.append((EvidenceField.TAG, tag, tag_index))

    selected: dict[tuple[str, EvidenceField], _Candidate] = {}
    for evidence_field, text, source_order in sources:
        source_candidates: list[_Candidate] = []
        for compiled in _COMPILED_ALIASES:
            for match in compiled.pattern.finditer(text):
                if not _context_allows(
                    compiled.alias.context_rule,
                    evidence_field,
                    text,
                    match,
                ):
                    continue
                match_kind = compiled.alias.match_kind
                if evidence_field is EvidenceField.TAG:
                    match_kind = MatchKind.EXACT_ALIAS
                source_candidates.append(
                    _Candidate(
                        evidence=SkillEvidence(
                            skill_code=compiled.skill_code,
                            skill_name=compiled.skill_name,
                            evidence_field=evidence_field,
                            matched_alias=_collapse_whitespace(match.group(0)),
                            evidence_text=_evidence_snippet(
                                text,
                                match.start(),
                                match.end(),
                            ),
                            rule_id=compiled.alias.rule_id,
                            match_kind=match_kind,
                        ),
                        source_order=source_order,
                        start=match.start(),
                        matched_length=match.end() - match.start(),
                    )
                )

        for candidate in source_candidates:
            if _is_part_of_longer_match(candidate, source_candidates):
                continue
            key = (candidate.evidence.skill_code, evidence_field)
            current = selected.get(key)
            if current is None or candidate.selection_key() < current.selection_key():
                selected[key] = candidate

    return tuple(
        candidate.evidence
        for candidate in sorted(
            selected.values(),
            key=lambda item: (
                item.evidence.skill_code,
                _FIELD_ORDER[item.evidence.evidence_field],
                item.evidence.rule_id,
            ),
        )
    )


def _context_allows(
    context_rule: ContextRule | None,
    evidence_field: EvidenceField,
    text: str,
    match: re.Match[str],
) -> bool:
    if context_rule is None:
        return True
    if evidence_field is EvidenceField.TAG:
        return match.start() == 0 and match.end() == len(text)

    before = text[max(0, match.start() - 90) : match.start()].casefold()
    after = text[match.end() : min(len(text), match.end() + 90)].casefold()
    window = text[max(0, match.start() - 90) : min(len(text), match.end() + 90)]

    if context_rule is ContextRule.GO_LANGUAGE:
        return _has_language_context(before, after)
    if context_rule is ContextRule.C_LANGUAGE:
        return _has_language_context(before, after) or _has_c_family_list(after)
    if context_rule is ContextRule.REACT_FRAMEWORK:
        return _has_framework_context(before, after, include_experience_after=True)
    if context_rule is ContextRule.RUST_LANGUAGE:
        positive_context = _has_language_context(before, after)
        if not positive_context:
            return False
        return not _RUST_NON_TECH.search(window) or bool(
            re.search(
                r"\b(?:programming|software|developer|engineer|language|codebase)\b",
                window,
                re.IGNORECASE,
            )
        )
    if context_rule is ContextRule.FOUNDRY_WEB3:
        return _has_web3_tool_context("foundry", before, after, window)
    if context_rule is ContextRule.ANGULAR_FRAMEWORK:
        return _has_framework_context(before, after)
    if context_rule is ContextRule.AZURE_CLOUD:
        return _has_azure_context(before, after)
    if context_rule is ContextRule.FLASK_FRAMEWORK:
        return _has_flask_context(before, after)
    if context_rule is ContextRule.HARDHAT_WEB3:
        return _has_web3_tool_context("hardhat", before, after, window)
    if context_rule is ContextRule.JAVA_LANGUAGE:
        return _has_language_context(before, after) or bool(
            re.match(r"^\s+experience\b", after)
        )
    if context_rule is ContextRule.VUE_FRAMEWORK:
        return _has_framework_context(before, after)
    if context_rule is ContextRule.KAFKA_STREAMING:
        return _has_kafka_context(window)
    if context_rule is ContextRule.PROMETHEUS_MONITORING:
        return _has_prometheus_context(window)
    if context_rule is ContextRule.SNOWFLAKE_DATA:
        return _has_snowflake_context(window)
    if context_rule is ContextRule.COSMOS_BLOCKCHAIN:
        return _has_cosmos_context(window)
    if context_rule is ContextRule.FIGMA_DESIGN:
        return _has_figma_context(window)
    if context_rule is ContextRule.SOLANA_TECHNICAL:
        return _has_solana_context(window)
    if context_rule is ContextRule.BASH_SHELL:
        return _has_bash_context(window)
    if context_rule is ContextRule.EXCEL_SPREADSHEET:
        return _has_excel_context(window)
    if context_rule is ContextRule.SPARK_DATA:
        return _has_spark_data_context(window)
    if context_rule is ContextRule.POSITIONING_MARKETING:
        return _has_positioning_marketing_context(window)
    if context_rule is ContextRule.AIRFLOW_INFRA:
        return _has_airflow_infra_context(window)
    return False


def _has_language_context(before: str, after: str) -> bool:
    return bool(
        re.match(
            r"^\s+(?:developer|engineer|programmer|programming|language)\b",
            after,
        )
        or re.search(
            r"(?:must\s+know|experience\s+(?:with|in)|"
            r"(?:written|built)\s+in)\s*$",
            before,
        )
        or re.search(
            r"(?:experience\s+)?(?:building|developing)\s+"
            r"(?:\w+\s+){0,4}(?:services?|applications?|systems?)\s+in\s*$",
            before,
        )
    )


def _has_framework_context(
    before: str,
    after: str,
    *,
    include_experience_after: bool = False,
) -> bool:
    after_terms = "developer|engineer|framework|application|app"
    if include_experience_after:
        after_terms = f"{after_terms}|experience"
    return bool(
        re.match(rf"^\s+(?:frontend\s+)?(?:{after_terms})\b", after)
        or re.search(
            r"experience\s+(?:with|in)\s*$",
            before,
        )
    )


def _has_c_family_list(after: str) -> bool:
    return bool(
        re.match(
            r"^\s*(?:,|/|\|)\s*(?:c\+\+|c#)"
            r"(?:\s*(?:,|and|/|\|)\s*(?:c\+\+|c#))*"
            r"\s+(?:developer|engineer|programmer)\b",
            after,
        )
    )


def _has_azure_context(before: str, after: str) -> bool:
    return bool(
        re.match(
            r"^\s+(?:cloud|developer|engineer|devops|services?|platform)\b",
            after,
        )
        or re.search(r"experience\s+(?:with|in)\s*$", before)
        or re.search(r"(?:deployed|hosted|running)\s+(?:on|in)\s*$", before)
    )


def _has_flask_context(before: str, after: str) -> bool:
    return bool(
        re.match(
            r"^\s+(?:developer|engineer|framework|api|application|app)\b",
            after,
        )
        or re.search(r"(?:python|experience\s+(?:with|in))\s*$", before)
    )


def _has_web3_tool_context(
    tool: str,
    before: str,
    after: str,
    window: str,
) -> bool:
    if re.search(rf"\b(?:palantir|data)\s+{tool}\b", window, re.IGNORECASE):
        return False
    return bool(
        re.match(
            r"^\s+(?:smart\s+contract\s+tooling|"
            r"for\s+(?:solidity|ethereum|smart\s+contract)\s+development)\b",
            after,
        )
        or re.search(r"(?:ethereum|solidity)\s+development\s+with\s*$", before)
        or re.search(
            r"(?:ethereum|solidity)\s+smart\s+contracts?"
            r"[^.!?\n]{0,60}\b(?:using|with)\b[^.!?\n]{0,40}$",
            before,
        )
    )


def _has_excel_context(window: str) -> bool:
    if re.search(r"\b(?:you\s+can\s+|where\s+you\s+|to\s+)?excel\b", window) and not re.search(
        r"\b(?:microsoft|ms|spreadsheet|pivot|vba|advanced|formulas?)\b", window
    ):
        return False
    return bool(
        re.search(
            r"\b(?:microsoft|ms)\s+excel\b|"
            r"\bexcel\s+(?:skills?|formulas?|pivot|vba|spreadsheet|data)\b|"
            r"\b(?:advanced|proficient\s+in|experience\s+(?:with|in)|skilled\s+in)\s+excel\b|"
            r"\b(?:spreadsheet|pivot\s+tables?|vba)\b[^.!?\n]{0,40}\bexcel\b",
            window,
            re.IGNORECASE,
        )
    )


def _has_spark_data_context(window: str) -> bool:
    if re.search(r"\bspark(?:ed|s|ling)?\b", window) and not re.search(
        r"\b(?:apache|scala|pyspark|big\s+data|streaming|cluster|distributed)\b",
        window,
    ):
        return False
    return bool(
        re.search(
            r"\bapache\s+spark\b|"
            r"\bspark\s+(?:sql|streaming|cluster|dataframes?|scala|pyspark)\b|"
            r"\b(?:scala|pyspark|big\s+data|data\s+engineering|distributed\s+computing)\b"
            r"[^.!?\n]{0,40}\bspark\b",
            window,
            re.IGNORECASE,
        )
    )


def _has_positioning_marketing_context(window: str) -> bool:
    if re.search(
        r"\b(?:css|layout|flexbox|grid|absolute|relative|gps|satellite)\b", window
    ):
        return False
    return bool(
        re.search(
            r"\b(?:brand|product|messaging|gtm|go-to-market|campaign|marketing|"
            r"market|customer|communication)\b[^.!?\n]{0,60}\bpositioning\b|"
            r"\bpositioning\b[^.!?\n]{0,60}\b(?:brand|product|messaging|gtm|"
            r"campaign|marketing|statement)\b",
            window,
            re.IGNORECASE,
        )
    )


def _has_airflow_infra_context(window: str) -> bool:
    return bool(
        re.search(
            r"\bapache\s+airflow\b|"
            r"\bairflow\s+(?:dag|dags|pipeline|orchestration|scheduler)\b|"
            r"\b(?:data\s+pipeline|workflow\s+orchestration|dag|etl)\b"
            r"[^.!?\n]{0,40}\bairflow\b",
            window,
            re.IGNORECASE,
        )
    )


def _has_kafka_context(window: str) -> bool:
    if re.search(r"\bFranz\s+Kafka\b", window, re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"\b(?:streaming|event\s+streams?|message\s+broker|middleware|"
            r"tech\s+stack|spring\s*boot|k8s|kubernetes|redis|mongodb|mysql)\b",
            window,
            re.IGNORECASE,
        )
    )


def _has_prometheus_context(window: str) -> bool:
    return bool(
        re.search(
            r"\b(?:monitoring|observability|metrics?|grafana|middleware|"
            r"tech\s+stack|spring\s*boot|k8s|kubernetes|redis)\b",
            window,
            re.IGNORECASE,
        )
    )


def _has_snowflake_context(window: str) -> bool:
    return bool(
        re.search(
            r"\b(?:data\s+engineer|data\s+warehouse|analytics|sql|dbt|"
            r"bigquery|databricks|airflow|cloud|tech\s+stack)\b",
            window,
            re.IGNORECASE,
        )
    )


def _has_cosmos_context(window: str) -> bool:
    return bool(
        re.search(
            r"\b(?:blockchain|web3|nodes?|chains?|sdk)\b",
            window,
            re.IGNORECASE,
        )
    )


def _has_figma_context(window: str) -> bool:
    return bool(
        re.search(
            r"(?:\b(?:use|using|fluent\s+in|proficient\s+with)\s+figma\b|"
            r"\bfigma\s+(?:ai|design(?:er)?)\b|"
            r"\btooling\s+such\s+as\s+figma\b|"
            r"\bdesign\b[^.!?\n]{0,60}\bfigma\b)",
            window,
            re.IGNORECASE,
        )
    )


def _has_solana_context(window: str) -> bool:
    if re.search(r"\bSolana\s+Foundation\b", window, re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"(?:\b(?:experience|familiarity)\b[^.!?\n]{0,70}\bsolana\b|"
            r"\bsolana\b[^.!?\n]{0,70}\b(?:experience|indexer|sdk|"
            r"development|programming|smart\s+contracts?)\b|"
            r"\b(?:developer|engineer|indexer)\b[^.!?\n]{0,50}\(?\bsolana\b|"
            r"\bsolana\b[^.!?\n]{0,50}\b(?:developer|engineer|indexer)\b)",
            window,
            re.IGNORECASE,
        )
    )


def _has_bash_context(window: str) -> bool:
    return bool(
        re.search(
            r"\b(?:shell|script(?:s|ed|ing)?|automation|terminal|"
            r"command[ -]line|cli|devops|sre)\b",
            window,
            re.IGNORECASE,
        )
    )


def _is_part_of_longer_match(
    candidate: _Candidate,
    candidates: list[_Candidate],
) -> bool:
    candidate_end = candidate.start + candidate.matched_length
    return any(
        other.matched_length > candidate.matched_length
        and other.start <= candidate.start
        and candidate_end <= other.start + other.matched_length
        for other in candidates
    )


def _evidence_snippet(text: str, start: int, end: int) -> str:
    max_context = 55
    left = max(0, start - max_context)
    right = min(len(text), end + max_context)

    if left > 0:
        next_whitespace = next(
            (index for index in range(left, start) if text[index].isspace()),
            None,
        )
        if next_whitespace is not None:
            left = next_whitespace + 1
    if right < len(text):
        previous_whitespace = next(
            (index for index in range(right - 1, end - 1, -1) if text[index].isspace()),
            None,
        )
        if previous_whitespace is not None:
            right = previous_whitespace

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
    return "".join(character if character.isprintable() else "�" for character in collapsed)
