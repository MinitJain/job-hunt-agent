# Licensing review

> **Internal notes on how the license was chosen.** The license itself is in [LICENSE](../LICENSE). Not legal advice.

Last updated: 2026-10-13.

## Decision

**GNU Affero General Public License v3.0 or later (`AGPL-3.0-or-later`)**, chosen 2026-10-13.

- Copyright holder: Minit Jain (single author).
- `LICENSE` contains the unmodified text from <https://www.gnu.org/licenses/agpl-3.0.txt>.
- The README has a copyright line, a plain-language summary and a note that n8n and the third-party services have their own terms.
- `scripts/sanitize_export.py` carries an SPDX identifier and copyright line. The workflow JSON files have none, since n8n exports have no place for comments; the repository-level `LICENSE` covers them.

## Goal and why AGPL

The goal was a real open-source license that stops people from taking the project, changing it and offering it as their own closed product.

- **AGPL** is OSI-approved open source. Anyone who distributes a copy, or runs a changed version as a network service for others, must make its source available under the same license. That rules out closed repackaging, including the most likely case for this project: a hosted "job hunt agent" service.
- AGPL does **not** forbid selling. Someone may charge for a copy or a hosted version, as long as they share the source under AGPL. Forbidding sale entirely would need a source-available license, which can't be called open source.

## Options considered

| License | Stops closed distributed copies | Stops closed hosted service | Stops resale | Open source |
|---|---|---|---|---|
| MIT (Cal.com, Hoppscotch) | No | No | No | Yes |
| GPL-3.0 | Yes | No | No | Yes |
| **AGPL-3.0 (Cap, Plane)** | **Yes** | **Yes** | No | **Yes** |
| FSL-1.1 | Yes | Yes | Yes (becomes MIT/Apache after 2 years) | No (source-available) |
| PolyForm Noncommercial 1.0.0 | Yes | Yes | Yes (also blocks all commercial use) | No (source-available) |

The licenses of the comparison projects were read from their repositories on 2026-10-13. Cap: AGPL-3.0, with some crates under MIT. Plane: AGPL-3.0. Cal.com: MIT; its root license changed from AGPL in April 2026. Hoppscotch: MIT.

## "Or later"

`or-later` lets recipients also use any later AGPL version the Free Software Foundation publishes. It is the common choice and keeps the project compatible with future versions.

## Things that still apply

- **Single author.** While the author is the only copyright holder, the license can still be changed for future versions. Before accepting outside contributions, decide whether to require a contributor agreement (CLA or DCO); without one, contributions arrive under AGPL and relicensing would need every contributor's consent.
- **n8n's own license.** The workflows need n8n to run. n8n is under the Sustainable Use License; this repository's license covers only the author's own work (workflow JSON, code, docs) and grants no rights to n8n. The README says so.
- **How copyleft applies to workflow JSON** imported into n8n is untested legal ground. The files are the source, so the source-sharing duty is easy to meet; the main practical effect is that copies must keep the notices and stay under AGPL.
- **Third-party APIs and data.** The license covers code, not job listings. API terms (see [release-review.md](release-review.md)) apply to whoever runs the workflow.
- **Prompts and generated text.** Prompts are part of the workflow files and covered by the same license. Generated drafts belong to whoever runs the workflow, subject to the LLM provider's terms; the AGPL does not apply to them.
- **Making the repository public** is a separate decision; see [release-review.md](release-review.md) for the items to settle first.
