# Release review checklist

**Internal planning document.** This lists what must be settled before the repository is made public. It is not legal advice, and nothing here grants or restricts any rights. Last reviewed: 2026-10-13.

## What is original and what is third-party

| Item | Origin | In this repository? |
|---|---|---|
| Workflow logic, Code-node JavaScript, prompts, validation rules, Tracker HTML/CSS | Original (author) | Yes |
| `scripts/sanitize_export.py`, documentation | Original (author) | Yes |
| n8n (runtime, node implementations) | n8n GmbH, Sustainable Use License | No; workflows only reference core node types |
| Community / third-party n8n nodes | — | None used |
| Copied snippets, templates, images, fonts | — | None identified |
| Job postings, generated drafts, execution data | Third-party / personal | No |

## Open questions

### Licensing
- [x] License chosen: AGPL-3.0-or-later (2026-10-13); see [licensing-review.md](licensing-review.md). `LICENSE` holds the unmodified text from gnu.org.
- [ ] Keep the repository single-author while possible, so the license can still be changed without anyone else's consent. Decide on a contributor agreement (or none) before accepting outside contributions.

### n8n
- [ ] The exports are JSON referencing n8n core node types and contain only original code; n8n's software is not redistributed. Confirm nothing in n8n's Sustainable Use License or terms restricts publishing your own workflow JSON. *(Believed fine, not formally checked.)*
- [ ] The n8n license covers n8n itself: use "only for your own internal business purposes or for non-commercial or personal use", and free, non-commercial redistribution. Make sure the README doesn't imply that people may run n8n commercially because of *this* repository's license.
- [ ] Trademark: the n8n license says use of its trademarks "is subject to applicable law". The repository name doesn't use "n8n"; check the wording in the description and README against n8n's brand guidance if one is published.
- [ ] Data Tables: confirm the feature is available in the n8n edition and version you tell people to use.

### Job sources (API terms)

Terms below were read on 2026-10-12 from each provider's public documentation and summarized; re-check before release.

| Source | What the provider says | Status in the workflow | Action |
|---|---|---|---|
| Remotive | Credit Remotive and link back to the Remotive URL; don't submit Remotive jobs to third-party sites (e.g. Google Jobs, LinkedIn); a few requests per day (suggested max 4); >2/min is blocked; jobs are delayed 24 h; don't use jobs to collect sign-ups/emails. | 1 request/day; Discord and Tracker show source name and URL. | [ ] Confirm attribution is sufficient. [ ] Document the limits for anyone who runs it more often. |
| Jobicy | Credit Jobicy and link to the canonical Jobicy URL; don't present listings as your own; polling at most once per hour; handle 429 with deferred retry. | 1 request/day; source URL shown. | [ ] Confirm attribution. |
| The Muse | Unregistered: 500 requests/hour. "Registration is required for any use beyond testing." API terms page not reviewed. | Called **without** an API key. | [ ] Register an app and add `api_key`, or document this. [ ] Read the API terms. |
| Arbeitnow | Free, no key; no terms found on the page reviewed. | 1 request/day. | [ ] Find and read Arbeitnow's API terms, if any. |
| Greenhouse Job Board API | Public per-company endpoint. Terms not reviewed. | Configured boards, 1 request each/day. | [ ] Review Greenhouse's terms for the Job Board API. |
| Lever Postings API | Public per-company endpoint. Terms not reviewed. | Configured boards, 1 request each/day. | [ ] Review Lever's terms for the Postings API. |

General: the repository contains **no job data**. Publishing the workflow is different from republishing listings. Don't add sample data, screenshots or fixtures containing real postings without checking the source's terms.

- [x] Company boards: the template ships with empty `atsBoards` (no employer targets); users add their own.
- [ ] The User-Agent sent to every source says "personal, non-commercial; runs once a day". Make sure that stays true for anyone running the public version, or change it to something neutral.

### LLM provider
- [ ] OpenRouter and the upstream provider (Google, for Gemini) process profile data and job text. Note this in the README for users (done) and check OpenRouter's terms and data-retention/training settings for your account.
- [ ] Generated text is the user's responsibility to check; the README says so. Consider whether the provider terms require anything beyond that for AI-generated content.

### Discord
- [ ] Only incoming webhooks are used (no bot, no OAuth app). No Developer Terms apply beyond normal Discord terms. Confirm webhook URLs are never committed (the sanitizer checks this).

### Privacy and security
- [ ] Re-run the sanitizer with a deny list on every export update and inspect the diff.
- [x] Regional defaults: the template has no workflow timezone, a neutral `locationPolicy`, no city/region filters in the source URLs, and the analysis prompt uses `profile.location`.
- [ ] The Tracker has no authentication and uses `GET` for writes; documented as a limitation. Decide whether to fix this before publishing, since people will copy it as-is.
- [ ] Keep raw n8n exports and backups out of the repository; they contain webhook URLs and the real profile. If a raw export is ever shared or committed, rotate the Discord webhooks.
- [ ] Execution data is saved for all executions (`saveDataSuccessExecution: all`), which keeps prompts and drafts in n8n's database. Document or change before recommending it to others.

### Quality
- [ ] Remaining naming leftovers from the earlier Ollama/Qwen version (code comments, sticky note, the `ollamaRequest` field name). The unused `ollamaUrl`/`ollamaTimeoutMs` keys are already removed from the template export.
- [ ] Optionally add tests: the Code-node logic (normalizers, validators) can be exercised outside n8n with fixtures.
- [ ] Add a screenshot of the Tracker and a Discord health message using fake data.
