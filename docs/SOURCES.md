# External Sources and Attribution

This document records external repositories, APIs, datasets, articles, and architectural references used during development.

We document external sources even when only an architectural idea or source list is reused.

---

## Source Template

### Source Name

URL:

License:

Used for:

- [ ] Code
- [ ] Architecture
- [ ] Dataset
- [ ] API discovery
- [ ] Source discovery
- [ ] General inspiration

What was used:

Notes:

---

## Active Vacancy Sources

### Remote OK

Official JSON API:
https://remoteok.com/api

Remote OK also advertises a public RSS feed, but the MVP integration uses only the JSON API.

Authentication:
None.

Attribution requirements:

- identify Remote OK as the source;
- preserve and expose the original Remote OK job URL;
- link back to Remote OK according to the legal notice embedded in the API response;
- do not use the Remote OK logo without written permission.

MVP source identity:

- `source_provider = "remote_ok"`;
- `source_scope = "global"`;
- `external_id` uses the source-native `id` field.

Fields currently used:

- `id`;
- `url`;
- `apply_url` when it is distinct from the Remote OK job URL;
- `position`;
- `company`;
- `description`;
- `location`;
- `tags` for conservative employment-type normalization;
- `date`, with `epoch` as a fallback for publication time.

Remote OK `salary_min` and `salary_max` remain preserved in the raw payload but are not normalized yet because the feed does not provide enough reliable currency and period context. The first array item may contain feed metadata and legal terms rather than a vacancy; the collector recognizes it as metadata and does not count it as a job.

No Remote OK code was copied. The integration was implemented against the public feed structure and its embedded attribution terms.

---

### Web3.career

Official API landing page:
https://web3.career/web3-jobs-api

Official API reference:
https://docs.bondex.app/api-reference

JSON endpoint:
https://web3.career/api/v1

Authentication:

- every request requires an API token in the `token` query parameter;
- the collector reads it from `WEB3_CAREER_API_TOKEN`;
- tokens must not be committed, logged, or exposed in client-side code;
- HTTPX query-token log redaction is installed before each request because INFO-level HTTPX logs otherwise include the full URL;
- free API access is requested through the official API landing page;
- the API documents `429` responses when its rate limit is exceeded.

Attribution and link-back requirements:

- identify Web3.career as the source;
- use the unmodified `apply_url` when directing users to a job;
- use a follow link (`rel="follow"` or no `rel` attribute);
- do not use `rel="nofollow"`;
- do not append tracking parameters to `apply_url`.

MVP source identity:

- `source_provider = "web3_career"`;
- `source_scope = "global"`;
- `external_id` uses only the source-native `id` field;
- `RawJob.source_url` preserves `url` when the API supplies a valid non-empty value;
- the live API may omit `url`, and a missing or null value does not invalidate the vacancy;
- no posting URL is synthesized from `id`, and `apply_url` is not copied into `source_url`;
- normalized `application_url` preserves the required, unmodified user-facing `apply_url` used for attribution and application.

Fields currently used:

- `id`;
- optional `url`, when supplied;
- required `apply_url`;
- `title`;
- `company`;
- `location`, with `city` and `country` as a fallback;
- `remote` or `is_remote` when explicitly boolean;
- `description` through the shared safe HTML-to-text converter;
- `tags`, preserved only in the original raw payload for later analysis;
- the first safely parsed value from `date`, `postedAt`, then `date_epoch`;
- disclosed `salary` text.

Salary distinction policy:

- only the officially documented `salary` field populates normalized `salary_text`;
- `salary_min_value`, `salary_max_value`, `salary_currency`, and `salary_unit` remain only in the original `RawJob.payload` until their provenance is documented explicitly;
- `estimated_min_salary`, `estimated_max_salary`, and `estimated_avg_salary` also remain raw-only and are not represented as employer-declared salary;
- normalized structured salary fields remain empty; salary text is not parsed into invented numbers, currency, or period.

The API currently returns a mixed top-level JSON array, normally with metadata strings and a nested jobs array. The collector searches for that nested array and also supports the documented direct-array fallback. The integration uses only the official JSON API and does not scrape Web3.career HTML listing pages.

No Web3.career or Bondex code was copied. The integration was implemented from the official API contract and terms.

---

## Candidate Repositories

### ever-jobs / ever-jobs

URL:
https://github.com/ever-jobs/ever-jobs

Status:
Candidate for evaluation.

Potential use:

- multi-source collector architecture
- job source discovery
- normalized job schemas
- API/RSS integration ideas

No code has been copied at this stage.

---

### Feashliaa / job-board-aggregator

URL:
https://github.com/Feashliaa/job-board-aggregator

Status:
Candidate for evaluation.

Potential use:

- ATS job collection
- Greenhouse
- Lever
- Ashby
- Workday
- large-scale company/job discovery

No code has been copied at this stage.

---

### speedyapply / JobSpy

URL:
https://github.com/speedyapply/JobSpy

Status:
Candidate for evaluation.

Potential use:

- job-board extraction reference
- LinkedIn / Indeed / Glassdoor coverage

No code has been copied at this stage.

---

## Rule

Before copying or adapting code from an external repository:

1. Check its license.
2. Record the repository here.
3. Record the files or concepts used.
4. Preserve any attribution required by the license.
5. Prefer adapting ideas over copying large code sections when practical.
