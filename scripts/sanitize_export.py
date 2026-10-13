#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Minit Jain
"""Sanitize an n8n workflow export before committing it to this repository.

Usage:
    python3 scripts/sanitize_export.py <export.json> <output.json> [--deny-file .sanitize-denylist]

What it changes:
  * keeps only the portable workflow fields (name, nodes, connections, settings, tags)
    and drops instance metadata (workflow id, versionId, instanceId, sharing/owner info,
    timestamps, static data, pinned data)
  * forces `active: false`
  * removes n8n credential ids (credential *names* are kept so nodes show which
    credential type to select after import)
  * replaces node ids and webhookIds with deterministic UUIDs derived from the
    workflow and node names (connections reference nodes by name, so logic is unchanged)
  * in the "Config & Profile" node: blanks every Discord webhook URL and replaces the
    whole `profile` object with a fictional example profile, and removes unused
    local-runtime leftovers (`ollamaUrl`, `ollamaTimeoutMs` and their comments)
  * template step (main workflow): replaces `config.locationPolicy` and `config.atsBoards`
    with neutral, commented defaults (no company boards), removes the city filters from
    The Muse request and the region filter from the Jobicy request, makes the analysis
    prompt use `profile.location` instead of a fixed country, renames "Daily 9:00 IST"
    to "Daily 9:00", and (both workflows) removes the workflow timezone so the instance
    timezone applies

What it checks afterwards (and refuses to write output on any hit):
  * Discord webhook URLs anywhere in the workflow
  * an `id` inside any node's `credentials` (at any depth)
  * email addresses other than @example.com, phone-number-like strings other than the
    example placeholder, and common token formats (Bearer, sk-/sk-or-, GitHub, Slack,
    Telegram bot, AWS, private-key blocks)
  * HTTP header/query/body parameters named like auth/token/key/secret that hold a
    literal value instead of using an n8n credential
  * any string in the optional deny file (one per line, case-insensitive)
It also warns about every URL host that is not in KNOWN_HOSTS, so new hosts get a
manual look.

Limits: only the "Config & Profile" node is rewritten. Personal data typed into any
other node, or a secret in a format not listed above, is only caught if it is in the
deny file or shows up in the host warnings. Always review `git diff` before committing.
Keep the deny file out of Git.
"""
import argparse
import json
import re
import sys
import uuid
from urllib.parse import urlparse

KEEP_TOP_LEVEL = ("name", "nodes", "connections", "settings", "tags")
CONFIG_NODE = "Config & Profile"
ID_NS = uuid.UUID("6f1c2a52-3b7e-4c39-9a51-0b8f2f1d7e10")
PHONE_PLACEHOLDER = "+00 00000 00000"

# Hosts the workflows are expected to reference. Anything else is reported for review.
KNOWN_HOSTS = {
    "localhost", "openrouter.ai", "www.arbeitnow.com", "remotive.com", "jobicy.com",
    "www.themuse.com", "boards-api.greenhouse.io", "api.lever.co", "api.ashbyhq.com",
    "api.smartrecruiters.com", "github.com", "www.linkedin.com", "example.com",
}

EXAMPLE_PROFILE = """const profile = {
  // EXAMPLE PROFILE — replace every value with your own REAL facts.
  // The generators may only use what is written here.
  name: 'Alex Example',
  email: 'alex@example.com',
  phone: '+00 00000 00000',

  // Country you live in / can work from. The analysis prompt scores location against it.
  location: 'Example Country',

  links: {
    github: 'https://github.com/your-username',
    linkedin: 'https://www.linkedin.com/in/your-profile/',
    portfolio: 'https://example.com/',
  },

  education: {
    status: 'third-year undergraduate student',
    degree: 'Bachelor of Engineering in Information Technology',
    institution: 'Example Institute of Technology',
    location: 'Example City, Example Country',
    expectedGraduation: '2028',
  },

  availability:
    'Available for a full-time internship during summer break; part-time during the semester.',

  targetRoles: [
    'Software Developer Intern',
    'Backend Engineer Intern',
    'Graduate Software Engineer',
  ],

  interests: [
    'developer tooling',
    'databases',
    'web services',
  ],

  skills: {
    languages: ['TypeScript', 'JavaScript', 'SQL', 'Python'],
    frontend: ['React', 'Tailwind CSS'],
    backend: ['Node.js', 'Express.js', 'REST APIs'],
    ai: [],
    databases: ['PostgreSQL', 'Redis'],
    devops: ['Docker', 'GitHub Actions', 'Linux'],
    other: ['Web services', 'Developer tooling'],
  },

  projects: [
    {
      name: 'Example Notes API',
      summary: 'REST API for personal notes with full-text search.',
      tech: ['Node.js', 'Express.js', 'PostgreSQL', 'Docker'],
      repo: 'https://github.com/your-username/example-notes-api',
      highlights: [
        'Built a REST API for creating, tagging and searching notes.',
        'Implemented PostgreSQL full-text search.',
        'Packaged the service with Docker.',
      ],
    },
    {
      name: 'Example Dashboard',
      summary: 'React dashboard that visualises data from a public API.',
      tech: ['React', 'TypeScript', 'Tailwind CSS'],
      repo: 'https://github.com/your-username/example-dashboard',
      highlights: [
        'Built a responsive dashboard with React and TypeScript.',
        'Added client-side caching of API responses.',
      ],
    },
  ],

  openSource: [
    {
      project: 'Example OSS Library',
      contribution: 'Fixed an off-by-one error in pagination and added a regression test.',
      tech: ['TypeScript'],
      url: 'https://github.com/example-org/example-lib/pull/1',
    },
  ],

  experience: [
    {
      role: 'Software Engineering Intern',
      organization: 'Example Company',
      location: 'Remote',
      start: '2025-06',
      end: '2025-08',
      bullets: [
        'Added input validation to three REST endpoints.',
        'Wrote integration tests for the billing service.',
      ],
    },
  ],
};
"""

WEBHOOK_URL_RE = re.compile(r"https://(?:[\w-]+\.)?discord(?:app)?\.com/api/webhooks/[^\s'\"`\\]+")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+\d{1,3}[\s-]?\(?\d{2,5}\)?[\s-]?\d{3,5}[\s-]?\d{0,5}")
URL_RE = re.compile(r"https?://[^\s'\"`\\)<>]+")
TOKEN_RES = {
    "Bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{12,}"),
    "sk-/sk-or- API key": re.compile(r"\bsk-(?:or-)?[A-Za-z0-9_-]{16,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "Telegram bot token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def sanitize_config_code(code: str) -> str:
    # Blank every Discord webhook URL (the workflow skips Discord when a URL is empty).
    code = WEBHOOK_URL_RE.sub("", code)
    # Replace the profile object: from `const profile = {` up to the closing `};` that
    # precedes the "Flat list" comment.
    new_code, n = re.subn(
        r"const profile = \{.*?\n\};\n(?=\s*// Flat list)",
        lambda _: EXAMPLE_PROFILE,
        code,
        flags=re.S,
    )
    if n != 1:
        sys.exit(f"error: could not locate the profile object in '{CONFIG_NODE}' (matches: {n})")
    # Drop local-runtime leftovers (unused config keys and comments about a local model runtime).
    for pattern, repl in CONFIG_CLEANUP:
        new_code = re.sub(pattern, repl, new_code, flags=re.M)
    for label, pattern, block in (
        ("locationPolicy", r"(?:[ \t]*//[^\n]*\n)*  locationPolicy: \{.*?\n  \},\n", TEMPLATE_LOCATION_POLICY),
        ("atsBoards", r"(?:[ \t]*//[^\n]*\n)*  atsBoards: \{.*?\n  \},\n", TEMPLATE_ATS_BOARDS),
    ):
        new_code, n = re.subn(pattern, lambda _, b=block: b, new_code, flags=re.S)
        if n != 1:
            sys.exit(f"error: could not locate config.{label} in '{CONFIG_NODE}' (matches: {n})")
    return new_code


# ---------------------------------------------------------------------------------------
# Template step: removes regional and job-target choices so the exported
# workflow is a neutral starting point. Every rule must match exactly once (or, for
# workflow settings, simply apply); a changed export makes the script stop instead of
# silently publishing personal settings.
# ---------------------------------------------------------------------------------------
# (regex, replacement) applied to the Config & Profile code; zero matches is fine.
CONFIG_CLEANUP = [
    (r"^[ \t]*// n8n runs in Docker.*\n", ""),
    (r"^[ \t]*ollamaUrl:.*\n", ""),
    (r"^[ \t]*ollamaTimeoutMs:.*\n", ""),
    (r"// Cost control:.*$", "// Cost control: keep runs bounded."),
]

TEMPLATE_LOCATION_POLICY = """  // EDIT: where you can work. Matching is a lower-case substring test.
  locationPolicy: {
    acceptRemote: true,

    // Remote jobs are kept when their region text is empty or contains one of these.
    // Add your country / region, e.g. 'europe', 'emea', 'latam', 'usa', 'canada', 'india', 'apac'.
    acceptedRemoteRegions: [
      'worldwide',
      'anywhere',
      'global',
    ],

    // On-site / hybrid jobs are kept only when their location contains one of these.
    // Empty = on-site jobs are all dropped. Add your country and cities, e.g. 'germany', 'berlin'.
    acceptedLocations: [],
  },
"""

TEMPLATE_ATS_BOARDS = """  // Direct company job boards via PUBLIC ATS APIs. No login, no scraping.
  // EDIT: add the companies you want to follow. Empty = source reported as NOT CONFIGURED.
  // `board` is the company's slug on that ATS. Check it first in a browser:
  //   Greenhouse: https://boards-api.greenhouse.io/v1/boards/<board>/jobs
  //   Lever:      https://api.lever.co/v0/postings/<board>?mode=json
  // Format: { board: '<slug>', company: '<display name>' }
  atsBoards: {
    greenhouse: [],
    lever: [],
  },
"""

SCHEDULE_RENAME = ("Daily 9:00 IST", "Daily 9:00")

# (node name, parameter, regex, replacement, rule kind). The patterns are generic on purpose:
# they must not contain anyone's actual cities, regions or country.
#   "strip":   remove every match (zero matches is fine: already neutral)
#   "country": must match exactly once, unless the line is already templated
COUNTRY = r"([A-Z][A-Za-z .'-]*?)"
PARAM_RULES = [
    # The Muse: keep the software / entry-level / remote filter, drop every other location filter.
    ("Fetch The Muse Jobs", "url", r"&location=(?!Flexible%20%2F%20Remote(?:&|$))[^&]*", "", "strip"),
    # Jobicy: drop any region filter (fetch all regions).
    ("Fetch Jobicy Jobs", "url", r"&geo=[^&]*", "", "strip"),
    # Analysis prompt: score location against profile.location instead of a fixed country.
    ("Prepare AI Analysis", "jsCode",
     rf"remote and open to candidates in {COUNTRY}, or located in \1; 10 = unclear; 0 = requires living or work authorization outside \1\.",
     "remote and open to candidates in ${profile.location}, or located in ${profile.location}; 10 = unclear; "
     "0 = requires living or work authorization outside ${profile.location}.", "country"),
    ("Prepare AI Analysis", "jsCode",
     rf"can a student who lives and studies in {COUNTRY} do this role from \1\?",
     "can a student who lives and studies in ${profile.location} do this role from ${profile.location}?", "country"),
    ("Prepare AI Analysis", "jsCode",
     rf"The candidate studies and lives in {COUNTRY}\.`",
     "The candidate studies and lives in ${profile.location}.`", "country"),
]


def apply_template(wf: dict) -> None:
    # Workflow timezone: drop it so the schedule follows the instance timezone (GENERIC_TIMEZONE).
    (wf.get("settings") or {}).pop("timezone", None)
    names = {n["name"] for n in wf["nodes"]}
    if CONFIG_NODE not in names:
        return  # Tracker: only the timezone applies
    old, new = SCHEDULE_RENAME
    if old in names:
        next(n for n in wf["nodes"] if n["name"] == old)["name"] = new
        if old in wf["connections"]:
            wf["connections"][new] = wf["connections"].pop(old)
        for outs in wf["connections"].values():
            for branches in outs.values():
                for branch in branches or []:
                    for link in branch or []:
                        if link.get("node") == old:
                            link["node"] = new
    for node_name, param, pattern, repl, kind in PARAM_RULES:
        node = next((n for n in wf["nodes"] if n["name"] == node_name), None)
        if node is None or not isinstance(node.get("parameters", {}).get(param), str):
            sys.exit(f"error: template rule target '{node_name}'.{param} not found")
        value = node["parameters"][param]
        new_value, n = re.subn(pattern, lambda _: repl, value)
        if kind == "country" and n != 1 and repl.split("${profile.location}")[0] + "${profile.location}" not in value:
            sys.exit(f"error: template rule for '{node_name}'.{param} matched {n} times (expected 1)")
        node["parameters"][param] = new_value


def sanitize(wf) -> dict:
    if isinstance(wf, list):
        if len(wf) != 1:
            sys.exit("error: expected a single workflow per export file")
        wf = wf[0]
    out = {k: wf[k] for k in KEEP_TOP_LEVEL if k in wf}
    out["active"] = False
    out["pinData"] = {}
    out["tags"] = out.get("tags") or []
    if not any(n["name"] == CONFIG_NODE for n in out["nodes"]) and "Tracker" not in out["name"]:
        print(f"warning: no '{CONFIG_NODE}' node found; profile not replaced", file=sys.stderr)
    apply_template(out)
    for node in out["nodes"]:
        for cred in (node.get("credentials") or {}).values():
            if isinstance(cred, dict):
                cred.pop("id", None)
        if "id" in node:
            node["id"] = str(uuid.uuid5(ID_NS, f"{out['name']}/node/{node['name']}"))
        if "webhookId" in node:
            node["webhookId"] = str(uuid.uuid5(ID_NS, f"{out['name']}/webhook/{node['name']}"))
        if node["name"] == CONFIG_NODE:
            node["parameters"]["jsCode"] = sanitize_config_code(node["parameters"]["jsCode"])
    return out


def credential_ids(wf: dict) -> list[str]:
    found = []

    def walk(o, node):
        if isinstance(o, dict):
            if "id" in o:
                found.append(node)
            for v in o.values():
                walk(v, node)
        elif isinstance(o, list):
            for v in o:
                walk(v, node)

    for node in wf["nodes"]:
        walk(node.get("credentials") or {}, node["name"])
    return found


SENSITIVE_PARAM_RE = re.compile(r"(?i)auth|token|secret|passw|api[-_]?key|apikey|cookie|signature")
SENSITIVE_QUERY_RE = re.compile(r"(?i)[?&](api[-_]?key|apikey|token|access_token|key|secret|signature)=([^&#'\"\s]+)")


def literal_secret_params(wf: dict) -> list[tuple[str, str]]:
    """HTTP header/query/body parameters with a secret-looking name and a literal (non-expression) value."""
    found = []
    for node in wf["nodes"]:
        p = node.get("parameters") or {}
        for field in ("headerParameters", "queryParameters", "bodyParameters"):
            for item in ((p.get(field) or {}).get("parameters") or []):
                name, value = str(item.get("name", "")), str(item.get("value", ""))
                if SENSITIVE_PARAM_RE.search(name) and value and not value.startswith("="):
                    found.append((node["name"], f"{field[:-10]} parameter"))
        url = str(p.get("url", ""))
        if not url.startswith("=") and SENSITIVE_QUERY_RE.search(url):
            found.append((node["name"], "URL query parameter"))
    return found


def check(wf: dict, text: str, deny: list[str]) -> tuple[list[str], list[str]]:
    """Returns (problems, warnings). Never includes the matched values themselves."""
    problems = []
    if WEBHOOK_URL_RE.search(text):
        problems.append("Discord webhook URL present")
    for node in credential_ids(wf):
        problems.append(f"credential id present in node '{node}'")
    emails = [e for e in EMAIL_RE.findall(text) if not e.lower().endswith("@example.com")]
    if emails:
        problems.append(f"{len(emails)} email address(es) not @example.com")
    phones = [p for p in PHONE_RE.findall(text) if p.strip() != PHONE_PLACEHOLDER and len(re.sub(r"\D", "", p)) >= 9]
    if phones:
        problems.append(f"{len(phones)} phone-number-like string(s)")
    for label, rx in TOKEN_RES.items():
        if rx.search(text):
            problems.append(f"{label} pattern present")
    for node, field in literal_secret_params(wf):
        problems.append(f"literal value in sensitive {field} of node '{node}' (use an n8n credential)")
    low = text.lower()
    problems += [f"deny-listed string #{i + 1} present" for i, s in enumerate(deny) if s.lower() in low]

    warnings = []
    hosts = {(urlparse(u).hostname or "") for u in URL_RE.findall(text)}
    for h in sorted(hosts - KNOWN_HOSTS - {""}):
        warnings.append(f"URL host not in KNOWN_HOSTS, review it: {h}")
    return problems, warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--deny-file", help="file with one forbidden string per line (kept out of Git)")
    args = ap.parse_args()

    with open(args.src, encoding="utf-8") as f:
        wf = sanitize(json.load(f))
    text = json.dumps(wf, indent=2, ensure_ascii=False) + "\n"

    deny = []
    if args.deny_file:
        with open(args.deny_file, encoding="utf-8") as f:
            deny = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        print("warning: no --deny-file given; your own name/contact details are not being checked", file=sys.stderr)
    problems, warnings = check(wf, text, deny)
    for w in warnings:
        print("warning: " + w, file=sys.stderr)
    if problems:
        sys.exit("refusing to write output:\n  - " + "\n  - ".join(problems))

    with open(args.dst, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {args.dst} ({len(wf['nodes'])} nodes)")


if __name__ == "__main__":
    main()
