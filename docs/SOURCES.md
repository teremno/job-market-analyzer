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
