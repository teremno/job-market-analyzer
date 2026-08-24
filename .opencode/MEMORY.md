# Project Memory — Job Market Analyzer

> Автоматично читається агентом на початку роботи в цьому проєкті.

## Суть проєкту
Дослідницька система збору й аналізу remote-вакансій: попит, навички, зарплати,
junior-доступність, AI-автоматизація. Live demo: https://jobpulse.support
(API: https://api.jobpulse.support).

## Стек і архітектура
- **Python** (type hints обов'язкові), pytest, ruff (.ruff_cache є)
- **SQLite**: головна БД `job-market.sqlite3` (~275 MB!) + окремі smoke-копії джерел:
  himalayas, jobicy, remote_ok, remotive, web3_career, we_work_remotely
- Пайплайн: External source → RawJob → NormalizedJobPosting → Repository →
  JobPosting → CanonicalJob (крос-джерельне лінкування ще НЕ реалізовано)
- Детермінована персистентність: UTC-таймстампи фіксованого формату, sorted JSON keys,
  Decimal без float, observation_hash + content_hash
- Docker (docker-compose.yml + prod), папки: src/, tests/, web/, docs/, deploy/
- Вебдашборд у web/

## Правила з AGENTS.md (критично!)
1. НЕ оверінжинірити: без мікросервісів/k8s/зайвих абстракцій
2. Інкрементально: одна чітко визначена задача за раз
3. Зміни архітектури — спершу пояснити what/why/alternatives/trade-offs
4. Зовнішній код → документувати в docs/SOURCES.md + перевірити ліцензію
5. Ієрархія джерел даних: REST API → GraphQL → RSS → public JSON → ATS → scraping.
   НЕ обходити auth/CAPTCHA/Cloudflare/rate limits
6. Секрети тільки через env; .env не комітиться

## Поточна фаза
Архітектура + MVP. Перша ціль: збір і нормалізація з невеликої кількості надійних джерел.
Документація рішень: docs/DECISIONS.md, SOURCES.md, ARCHITECTURE.md, PRODUCT_VISION.md,
ROADMAP.md. Великий PROJECT_HANDOFF.md (60KB) у корені — чекати при онбордингу.

## Уроки
(порожньо — заповнюється через скіл self-reflection)
