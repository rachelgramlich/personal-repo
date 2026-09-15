# Add GitHub issue (backlog or bug)

**Scope: issue capture only.** Create one GitHub issue and stop. Backlog features are implemented later with **`/work-on-enhancement <issue-number>`**; bugs are fixed in a normal fix PR (not the enhancement backlog).

## Use This Mac (local agent)

**Before running any issue CLI below**, tell the user:

> Issue creation works best on **This Mac** (local agent). If this chat is a **Cloud** agent, switch to **This Mac** on this repo and run **`/add-enhancement`** again — do not create the issue from Cloud.

- If the session is Cloud (or you are not sure), **stop after the reminder** and wait for the user to confirm they switched to This Mac.
- Only run `dev add-enhancement` / `dev report-bug` once you are on This Mac or the user confirms they are.

## Do not explore or implement

In this turn you must **not**:

- Search, grep, or read the codebase (no `src/`, `tests/`, configs, or other repo files).
- Run `dev work-on-enhancement`, `dev list-enhancements`, or any command except the issue CLI below.
- Create branches, commits, pull requests, or todos for implementation work.
- Start coding, planning implementation, or summarizing how the feature would be built.

Requires **`gh`** authenticated for this repo.

## Pick the template

| User intent | GitHub template | CLI |
|-------------|-----------------|-----|
| **New feature / improvement** (backlog) | **Grocery Wizard enhancement** | `dev add-enhancement` |
| **Something broken** (defect) | **Bug report** | `dev report-bug` |

When unsure, ask once: “Is this a backlog feature or a bug?”

### Enhancement backlog

- Issue gets the **`grocery-wizard`** label (clean title; no required prefix).
- **Expected behavior & manual test hints** are required (same as the GitHub form).

```bash
uv run python -m src.grocery_wizard dev add-enhancement \
  --title "<title>" \
  --description "<what should change and why>" \
  --expected-behavior "<surface, steps, expected results>" \
  --area <ui|parser|shopping|recipes|cli|other>
```

(Omit `--area` when `other`.)

### Bug report

- Uses the **Bug report** template (`bug` label). Not listed by `dev list-enhancements`.

```bash
uv run python -m src.grocery_wizard dev report-bug \
  --title "<title>" \
  --description "<summary>" \
  --repro "<numbered steps>" \
  --actual "<what happened>" \
  --expected "<what should happen>" \
  --context "<optional logs/screenshots>"
```

(Omit `--context` when empty.)

## Reply

Confirm the GitHub issue number and URL. For backlog items, note they can implement later with `/work-on-enhancement <issue-number>`.

Do **not** implement in this turn unless the user explicitly asks after the issue exists.
