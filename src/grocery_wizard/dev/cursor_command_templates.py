"""Embedded Cursor slash-command templates (installed locally via dev install-cursor-commands)."""

# ruff: noqa: E501

from __future__ import annotations

CURSOR_COMMAND_FILES: dict[str, str] = {
    "add-enhancement.md": """# Add enhancement (local backlog)

Capture a feature idea or improvement in `.local/grocery_wizard/enhancements.jsonl` for later implementation.

## How this relates to other dev logs

| Workflow | Storage | How you pick it up |
|----------|---------|-------------------|
| Ingredient parser fixes | `.local/grocery_wizard/ingredient_edits.jsonl` (UI edits) | `uv run python -m src.grocery_wizard dev suggest-fixes` aggregates patterns for parser work |
| **Enhancement backlog** | `.local/grocery_wizard/enhancements.jsonl` | **Use Cursor:** `/list-enhancements` then `/work-on-enhancement <id>` |

Prefer **`/add-enhancement`** in Cursor over typing `dev add-enhancement` in a terminal; the CLI remains for scripts and non-Cursor environments.

## Your task

The user may put details **after** the command name (title, description, area). Use that text; if anything is missing, ask once, then proceed.

1. **Title** (required): short one-liner.
2. **Description** (optional): longer context, acceptance hints, links.
3. **Area** (optional, default `other`): one of `ui`, `parser`, `shopping`, `recipes`, `cli`, `other`.

4. Append the entry **non-interactively**:

```bash
uv run python -m src.grocery_wizard dev add-enhancement \\
  --title "<title>" \\
  --description "<description>" \\
  --area <area>
```

(Omit `--description` or `--area` when empty / `other`.)

5. Confirm the printed ID (e.g. `enh_003`) and remind the user they can implement later with `/work-on-enhancement <id>`.

Do **not** start implementing the enhancement in this turn unless the user explicitly asks.
""",
    "list-enhancements.md": """# List enhancements

Show open items from the local enhancement backlog.

## Context

- Backlog file: `.local/grocery_wizard/enhancements.jsonl` (gitignored; local only).
- Ingredient edit logs (`.local/grocery_wizard/ingredient_edits.jsonl`) feed **`dev suggest-fixes`** for automatic parser suggestions; enhancements are **manual feature/fix ideas** you implement when you have time via **`/work-on-enhancement`**.

## Your task

1. Run:

```bash
uv run python -m src.grocery_wizard dev list-enhancements
```

2. If the user asked for closed/done items too:

```bash
uv run python -m src.grocery_wizard dev list-enhancements --all
```

3. Present the CLI output clearly (ID, area, title, status).

4. If there are open items, note: **`/work-on-enhancement <id>`** (e.g. `/work-on-enhancement enh_001`) to implement one.

Do not implement anything unless the user chooses an ID and asks you to work on it in this chat.
""",
    "work-on-enhancement.md": """# Work on enhancement

Pick up one backlog item and implement it end-to-end.

## Context

- Backlog: `.local/grocery_wizard/enhancements.jsonl`.
- **`dev suggest-fixes`** + `ingredient_edits.jsonl` = data-driven parser fix hints from UI edits.
- **Enhancements** = intentional backlog; primary UX is this command (not ad-hoc CLI).

## Your task

### 1. Resolve enhancement ID

- If the user typed an ID after the command (e.g. `/work-on-enhancement enh_002`), use it.
- Otherwise run `uv run python -m src.grocery_wizard dev list-enhancements`, show open items, and ask which ID to use. Stop until they pick one.

### 2. Load full instructions

Run and **follow** the printed prompt (includes title, description, area, files, branch name, close command):

```bash
uv run python -m src.grocery_wizard dev show-enhancement <ID>
```

Do **not** pass `--close` until the enhancement is actually shipped.

### 3. Implement

- `git fetch origin main` and create the branch named in the show-enhancement output (pattern `cursor/<slug>-21af` off `main`).
- Read the listed files and any other code needed for the area.
- Keep scope aligned with the enhancement description; match existing project style.
- If you change Python: `uv run ruff check` on touched paths; run relevant tests when they exist.

### 4. Ship

- Commit with a clear message referencing the enhancement ID.
- Push the branch and open or update a GitHub PR; mention `<ID>` and title in the PR body.

### 5. Close the backlog entry

When the work is merged or complete:

```bash
uv run python -m src.grocery_wizard dev close-enhancement <ID>
```

Summarize what you changed and link the PR for the user.
""",
    "work-all-enhancements.md": """# Work all enhancements (spawn workers)

Orchestrate **one worker per open backlog item**. Do not implement the enhancements yourself in this chat — only coordinate parallel workers.

## Context

- Backlog: `.local/grocery_wizard/enhancements.jsonl` (gitignored; local only).
- Spawn specs: `uv run python -m src.grocery_wizard dev spawn-enhancement-workers --json`

## Your task

1. Run:

```bash
uv run python -m src.grocery_wizard dev spawn-enhancement-workers --json
```

2. If the JSON array is empty, say the backlog has no open items and stop.

3. For **each** object in the array, start a worker **in parallel** (as many concurrent workers as the environment allows):

   - **Cloud Agent (preferred on desktop):** start a new Cloud Agent on this repo with `agent_message` as the first message (or paste the full `prompt` field).
   - **In-agent subagents:** launch a Task with `subagent_type=best-of-n-runner` and set the task description to `"<id>: <title>"`. Pass the full `prompt` string as the task instructions.

4. After launching, summarize for the user: enhancement ID, title, branch, and how each worker was started (URL if known).

5. Do **not** run `dev close-enhancement` from this orchestrator chat — each worker closes its own item when shipped.

Optional: reinstall slash commands after pulling this template:

```bash
uv run python -m src.grocery_wizard dev install-cursor-commands
```
""",
}
