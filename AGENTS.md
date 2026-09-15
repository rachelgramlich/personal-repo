# Agent instructions (grocery_wizard)

## Issues (slash commands = primary UX)

| You type | Purpose |
| --- | --- |
| **`/create-issues`** | One or more notes → auto **bug vs backlog**, merge by **code area**, create GitHub issue(s) |
| **`/architecture-review`** | **Phase A:** standards audit report + Ruff/CI gap analysis; **Phase B:** file **`audit`**-labeled issues (`dev create-issues --audit`) |
| **`/list-enhancements`** | Open backlog (grocery-wizard label) |
| **`/work-on-issue N`** | Full implementation brief for backlog **or** bug #N |

Slash files: `.cursor/commands/create-issues.md`, `architecture-review.md`, `list-enhancements.md`, `work-on-issue.md`.

Agents run the matching CLI when structured output or `gh` is needed:

- `dev create-issues` — `--dry-run` to preview; `--item` (repeat) or stdin; `--plan-file` for edited JSON; `--audit` for architecture-review follow-ups
- `dev list-enhancements`
- `dev work-on-issue <issue-number>`

**Create issues on This Mac** when possible (`gh` auth). Cloud agents should ask the user to switch before running `create-issues`.

### Backlog ship checklist (enhancements)

1. PR title: `dev enhancement-pr-title <issue-number>`
2. PR template **Manual verification** + `Closes #<issue-number>`
3. After user confirms manual UAT: `dev record-manual-verification <issue-number>`

Do not close backlog issues by hand — merge with `Closes #N`.

One-time: `dev migrate-enhancements-to-github`, `dev backfill-enhancement-labels`.

## Dev CLI (maintenance)

`uv run python -m src.grocery_wizard dev --help`

| Area | Commands |
| --- | --- |
| **Notion ingredients** | `backfill-ingredients`, `reconcile-ingredients`, `refresh-all-ingredients`, `reformat-ingredients`, `audit-recipes`, `show-schema` |
| **Parser hints from UI** | `suggest-fixes` (`.local/grocery_wizard/ingredient_edits.jsonl`) |
| **Pipeline check** | `validate-pipeline` |
| **Prod feedback log** | `list-feedback` |

After `just setup`, Streamlit’s `developing-with-streamlit` skill is under `.cursor/skills/` for UI work.
