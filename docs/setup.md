# Setup

Steps marked **(unverified)** have not been tested end-to-end from this repository. The other steps describe the exported workflows as they are.

## Requirements

- An n8n instance with **Data Tables** available. The workflows were developed against **n8n 2.40.7** (Docker image `docker.n8n.io/n8nio/n8n`). Older versions may lack Data Tables or the node versions used (Data Table 1.1, HTTP Request 4.2, Merge 3.2, Code 2, Webhook 2).
- For the local route below: Docker with Docker Compose.
- An [OpenRouter](https://openrouter.ai) account and API key with credit.
- Optional: two Discord channels with incoming webhooks (one for jobs, one for health reports).

No community nodes and no external database are needed. The only environment variables are n8n's own: the timezone (`GENERIC_TIMEZONE`, `TZ`) and, when n8n is not reached at `http://localhost:5678`, `WEBHOOK_URL`.

## 1. Run n8n locally

```sh
docker compose up -d
# editor: http://localhost:5678
```

`compose.yaml` stores data in the `n8n_data` volume and sets the instance timezone to `UTC`. **Set `GENERIC_TIMEZONE` and `TZ` to your own IANA timezone** (e.g. `Europe/Berlin`). The exported workflows carry no timezone of their own, so the **Daily 9:00** schedule fires at 09:00 in the instance timezone. To override it for one workflow, open the workflow's **Settings → Timezone** in n8n. If you run n8n some other way, set `GENERIC_TIMEZONE` in that environment.

## 2. Create the OpenRouter credential

In n8n: **Credentials → New → Header Auth**

- Name: anything (the export refers to it as `Header Auth account`)
- Header name: `Authorization`
- Header value: `Bearer <your OpenRouter API key>`

The key stays in n8n's credential store. Never paste it into a Code node, a URL or the Tracker.

## 3. Import the workflows

**Workflows → Import from file**, once for each file in `workflows/`. Both import inactive.

In the main workflow, open these four nodes and select your credential:

- Analyze Job with Gemini
- Generate Tailored Resume with Gemini
- Generate Cover Letter with Gemini
- Generate Application Answers with Gemini

## 4. Configure `Config & Profile`

Open the **Config & Profile** Code node in the main workflow.

1. **Replace the example `profile`** with your real details. The generators and validators treat it as the only source of truth: anything missing here cannot appear in a draft, and anything wrong here will. Keep the structure (`skills` groups, `projects[].tech`, `projects[].highlights`, `experience[].bullets`, `openSource`).
2. **Discord** (optional): in Discord, open a channel's **Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL**, and paste the URLs into `discord.jobsWebhookUrl` and `discord.healthWebhookUrl`. Empty means "don't send"; the health report is still written to `job_hunt_runs`. A webhook URL lets anyone post to that channel: keep it private and never commit it.
3. **ATS boards** (empty in the template, so Greenhouse and Lever report `NOT CONFIGURED`): add `{ board: '<slug>', company: '<name>' }` entries to `atsBoards.greenhouse` / `atsBoards.lever` for companies you want to follow. The slug is the company's identifier in that ATS, usually visible in its careers-page URL. A board slug must exist (check `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` or `https://api.lever.co/v0/postings/<slug>?mode=json` in a browser first); a wrong slug shows up as a failed board in the health report.
4. **Location** (review before the first run; the template defaults to worldwide-remote only):
   - `profile.location`: the country you live in / can work from. The analysis prompt scores location fit against it.
   - `config.locationPolicy.acceptedRemoteRegions`: remote jobs are kept when their region text is empty or contains one of these lower-case keywords (default `worldwide`, `anywhere`, `global`). Add your country or region, e.g. `europe`, `usa`, `india`.
   - `config.locationPolicy.acceptedLocations`: on-site and hybrid jobs are kept only if their location contains one of these. **Empty by default, which drops every on-site job**; add your country and cities.
   - Source URLs, in the **Fetch …** nodes: The Muse is filtered to `Flexible / Remote` only (add `&location=City%2C%20Country` parameters for your cities, in The Muse's location format); Jobicy is fetched for all regions (add its `geo` parameter to narrow it); Remotive and Arbeitnow have no location filter.
5. **Other filters**: `maxYearsExperience`, `minMatchScore`, `minSkillsScore`, `maxAiJobsPerRun`, `maxPackagesPerRun`, `applicationQuestions`, `model`.
6. **Tracker URL**: the template assumes `http://localhost:5678`. If your n8n is reached at any other address, set `trackerBaseUrl` here (used for the links in Discord messages) **and** edit the hard-coded `base`/`url` constants in the Tracker's **Render Job List**, **Render Job Page** and **Build Redirect** nodes. Use the plain base URL only; never add a token or password to it (see [Protect the Tracker](#protect-the-tracker)).

Whenever you change the profile, also update `PROFILE_UPDATED_AT` in Render Job List and Render Job Page, so older rows are labelled "historical".

The fixed source URLs (Arbeitnow, Remotive, Jobicy, The Muse filters) live in the **Fetch …** nodes, not in the config.

## 5. First run

1. Open the main workflow and click **Execute workflow**. The first run creates the Data Tables `job_hunt_jobs` and `job_hunt_runs`; the Tracker reads `job_hunt_jobs` and fails until it exists.
2. Check:
   - the `run_summary` row in `job_hunt_runs` (**Data tables** in the n8n sidebar), or the Discord health channel: every active source should be ✅ or have a clear ❌ reason, and unconfigured sources show ⚙️;
   - any `analysis_error` rows in `job_hunt_runs`.
3. Activate the **Tracker** workflow (newer n8n versions label this **Publish**). Its webhooks answer on the production URL `/webhook/job-hunt…` only while it is active; the `/webhook-test/…` URL works only while the editor is listening. Open `http://localhost:5678/webhook/job-hunt` to see the analyzed jobs.
4. When satisfied, activate (publish) the main workflow for the daily schedule.

A second run on the same day will mostly find no unseen jobs; it still sends a health report.

## Protect the Tracker

The exported Tracker has **no authentication**, and all three webhooks (`/webhook/job-hunt`, `/webhook/job-hunt/job`, `/webhook/job-hunt/status`) are plain `GET` endpoints. Anyone who can reach them can read every stored job, including your generated resumes and contact details, and can change statuses and notes.

On `localhost` this is only reachable from your own machine. **Before n8n is reachable from any other machine, protect all three webhooks**, not just the list page. Options **(unverified, not part of the exported workflows)**:

- keep n8n on a private network or VPN only; or
- put n8n behind a reverse proxy that requires authentication for `/webhook/job-hunt*`; or
- enable *Authentication* on all three Webhook nodes. The Tracker is used from a browser by following links and submitting a form, so it needs a method the browser handles by itself, such as Basic Auth. Header- or token-based methods would need something outside the browser to add the header.

Do **not** put credentials in browser-visible places: not in `trackerBaseUrl`, the Tracker's HTML, link query strings, or the Discord messages (they include Tracker links).

## Running n8n on a server (unverified)

Nothing in the workflows is tied to a particular host apart from the tracker URLs and the timezone. Wherever you run n8n:

- configure your own endpoints: `WEBHOOK_URL` (the public base URL, so n8n generates correct webhook URLs), `trackerBaseUrl` and the three Tracker constants from step 4.6, and your Discord webhook URLs;
- protect the Tracker as described above before it is reachable;
- use a persistent volume or database for n8n data, otherwise Data Tables and execution history are lost on restart;
- make sure the instance is running at 09:00 in its timezone (not suspended or asleep), or the schedule won't fire;
- create the OpenRouter credential again on that instance; credentials are not part of the exports.

## Updating the exports in this repository

Never commit a raw export: it contains your profile, Discord webhook URLs and instance ids.

1. In n8n, **Download** the workflow to a location outside this repository.
2. Create a deny-list file **outside the repository** (or name it `.sanitize-denylist`, which is git-ignored) with one string per line that must never be committed: your name, email, phone number, institution, employer names, webhook ids, your n8n hostname.
3. Run:
   ```sh
   python3 scripts/sanitize_export.py ~/Downloads/export.json workflows/job-hunt-agent-v2.json --deny-file .sanitize-denylist
   ```
   The script replaces the profile, blanks Discord URLs, removes unused local-runtime config keys, credential ids, instance metadata and pinned data, regenerates node and webhook ids, applies the template defaults, and sets `active: false`. It refuses to write if a Discord webhook URL, credential id, non-example email address, phone-number-like string, common token format (Bearer, `sk-`, GitHub, Slack, Telegram, AWS, private key), a literal value in a secret-named HTTP header/query/body parameter, or a deny-listed string remains. It warns about every URL host it does not recognise.
4. Review `git diff` before committing. The script is a safety net, not a guarantee: it rewrites only the `Config & Profile` node plus a fixed list of template rules (two source URLs, three lines of the analysis prompt, the schedule node name, the workflow timezone), and personal data or a secret in an unrecognised format elsewhere is caught only if it is in your deny list. If your export no longer matches a template rule, the script stops instead of guessing. Note that `.gitignore` ignores JSON outside `workflows/`, but a raw export saved *into* `workflows/` would not be ignored.
