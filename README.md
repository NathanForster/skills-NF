# skills-NF

A collection of reusable skills for software development workflows, usable from both [Claude Code](https://claude.ai/code) and GitHub Copilot.

Each skill lives in its own folder under [`skills/`](skills/), in the open [Agent Skills](https://agentskills.io/specification) format: a `SKILL.md` plus any scripts and references it bundles. Claude Code and GitHub Copilot (VS Code, Copilot CLI, cloud agent) both read that format, so one copy serves both tools. Invoke any skill as `/name`, or let the tool choose it from its description.

## Skills at a glance

| Skill | What it does |
|-------|--------------|
| [`/handoff`](skills/handoff/SKILL.md) | Session continuity — load context at start, update `HANDOFF.md` at end |
| [`/icm-validate`](skills/icm-validate/SKILL.md) | Audit ICM requirement statuses against code and pipeline artifacts |
| [`/session-close`](skills/session-close/SKILL.md) | Full end-of-session checklist — validate, test, document, commit |
| [`/docs-review`](skills/docs-review/SKILL.md) | Deep review, cross-reference, and backfill of the docs folder, plus composite PDF rebuild |
| [`/build-docs`](skills/build-docs/SKILL.md) | Build the consolidated documentation-set PDF (or render a single Markdown file) via the shared docset engine |
| [`/run-mode`](skills/run-mode/SKILL.md) | Launch the project's app in a named mode, driven by a `RUN.md` mode registry |
| [`/humanizer`](skills/humanizer/SKILL.md) | Edit text so it reads less like an LLM wrote it: substance and structure first, then phrasing |

## Installation

1. Clone the repo:
   ```bash
   git clone https://github.com/NathanForster/skills-NF.git
   ```

2. Copy each skill folder you want (the whole folder, not just `SKILL.md`) into your personal skills directories:
   ```
   ~/.claude/skills/<name>/     # Claude Code, and Copilot in VS Code
   ~/.copilot/skills/<name>/    # Copilot CLI, and Copilot in VS Code
   ```
   On Windows, `~` is `C:\Users\<you>`.

   Or, to scope a skill to a single project, put its folder in that repo's `.claude/skills/`. Claude Code, Copilot in VS Code, Copilot CLI and the Copilot cloud agent all read that location, and the skill travels with the project.

3. For `/build-docs`, also copy [`lib/`](lib/) to `~/.claude/commands/lib/`. That is where the shared docset engine is looked up, by the skill and by projects' own build scripts.

4. Start a new session. An already-open Claude Code session can keep serving a cached copy until its skill list refreshes.

### Where each skill can run

Personal skills exist only on the machine they are installed on. The Copilot cloud agent runs on GitHub's machines, so it only sees skills committed to a repo, and cannot reach local paths or local tooling. `/handoff`, `/session-close`, `/build-docs` and `/run-mode` work with a local checkout, so use them from Claude Code, Copilot in VS Code or Copilot CLI. `/humanizer` and `/docs-review` carry what they need and also work as project skills.

## Skills

### `/handoff`

A session continuity helper that keeps long-running projects moving across Claude Code context resets.

- `/handoff start` — Reads the project's `HANDOFF.md` and surfaces everything needed to resume work immediately: in-progress tasks, recent decisions, blockers, and next steps.
- `/handoff end` — Prompts for what changed this session and updates `HANDOFF.md` so the next session starts clean.

Pairs well with a `HANDOFF.md` file checked into your project root — if the file doesn't exist yet, the skill offers to create it from a built-in template.

---

### `/icm-validate`

Validates implementation status for projects using the [Interpretable Context Methodology (ICM)](https://github.com/NathanForster/ICM) requirements framework.

Checks every requirement in the register against:
- Source code in `src/`
- Implementation briefs in `source-development/workflows/03-implementation/`
- Validation briefs in `source-development/workflows/04-validation/`

Updates the `Status` column in both the requirements register and traceability matrix with one of: `Baselined`, `Implemented`, `Verified`, or `Superseded`.

Pass a requirement ID — `/icm-validate REQ-42` — to validate a single requirement instead of the full register.

---

### `/session-close`

An end-of-session checklist for ICM-governed projects that runs the whole close-out in order:

1. **ICM validation** — runs `/icm-validate` (with its confirmation gate) to advance requirement statuses.
2. **Additional tests** — adds coverage for untested pure functions.
3. **Build & test** — builds and tests with the project's standard commands, fixing failures before continuing.
4. **Docs audit** — runs `/docs-review` over the documentation folder, assuming full backfill of every section now knowable, with DID-specific priority ordering for DoD projects. Skipped when there's no docs folder.
5. **Handoff** — runs `/handoff end` to update `HANDOFF.md` and produce the session summary.
6. **Commit & push** — a single commit covering everything (including `HANDOFF.md`), pushed to the current branch.

---

### `/docs-review`

A deep review-and-update pass over every document in a project's `docs/` (or `documentation/`) folder.

- **Per-document review** — reads each document in full, flagging incomplete sections, `TBD`/placeholder content, and anything that has drifted from the current code or requirements.
- **Cross-reference checks** — verifies identifiers, cross-document links, terminology, and duplicated facts agree across the whole suite.
- **Update & backfill** — after a findings-table confirmation, fixes stale content, backfills sections now knowable from the code/requirements/tests, and repairs cross-references (scoped `[TBD]`s where information genuinely doesn't exist yet).
- **Composite PDF** — if the folder contains a combined PDF, locates its `.py` build script and re-runs it to regenerate the PDF.

Pass a folder — `/docs-review documentation` — to target a specific directory and skip auto-detection.

---

### `/build-docs`

Builds a project's **consolidated documentation-set PDF** — a single bookmarked file assembled from many Markdown docs, with a cover, a clickable table of contents, and per-part section covers. It can also render a **single** Markdown file to a standalone PDF (`/build-docs single <in.md> <out.pdf> [landscape]`).

All the layout logic lives in one shared engine — [`lib/docset_builder.py`](lib/docset_builder.py) — so every project shares the same (heavily battle-tested) table pagination, column-width fitting, cross-page header repetition, keep-heading-with-content, and silent-truncation verification. Projects supply only *which* documents to include:

- **Data-file form** — a `DOCSET.json` at the repo root (see [`lib/DOCSET.example.json`](lib/DOCSET.example.json)) listing the parts, documents, titles, and per-doc landscape flags. Run directly: `python lib/docset_builder.py DOCSET.json`.
- **Build-script form** — a tiny `orchestrator/build_docset_pdf.py` (or similar) that imports the engine and loads the project's config. Keeping a `.py` entry point means `/docs-review` finds and runs it automatically.

Requires `pymupdf`, `markdown-it-py`, `pypdf`, `beautifulsoup4` in the project's Python.

#### Adopting the docset builder in another project

Paste the prompt below into a fresh Claude session **in the target project**. It is
self-contained — it tells Claude to reference the shared engine (never copy it),
propose a `DOCSET.json` from the project's own `docs/`, add a thin build script, and
verify the result.

````text
Set this project up to build a consolidated documentation-set PDF using the shared
docset engine (not a per-project copy).

BACKGROUND
- The shared engine lives in my skills repo:
  https://github.com/NathanForster/skills-NF  ->  lib/docset_builder.py
- On this machine it should be at:  ~/.claude/commands/lib/docset_builder.py
  (the user-level copy, synced from that repo). If it is missing, check the repo
  checkout (e.g. C:\.ai\.claude\commands\lib); if both are missing, tell me and
  stop (I may need to `git pull` that repo and re-run its sync).
- It renders Markdown -> PDF with automatic table column-fitting, cross-page header
  repetition, keep-heading-with-its-content, and silent-truncation verification.
- Python deps (must be importable by the python you run): pymupdf, markdown-it-py,
  pypdf, beautifulsoup4. If an import fails, report the missing package -- do NOT
  hand-assemble a PDF.

DO THIS
1. Confirm the engine exists at one of: the CLAUDE_COMMANDS_LIB env var,
   ~/.claude/commands/lib, or the repo checkout (e.g. C:\.ai\.claude\commands\lib).
   Read its module docstring for the current API/CLI.
2. Inventory this project's docs/ folder. Propose a DOCSET.json structure --
   grouped into logical "parts", each doc with num/acr/file/title and a
   landscape flag (true only for wide tables, >~6 columns). SHOW me the proposed
   structure and wait for my confirmation before writing anything. Don't guess
   the order or invent documents.
3. On my OK, write DOCSET.json at the repo root. Format:
     {
       "title": "...", "subtitle": "...", "cover_lines": ["...", "..."],
       "docs_dir": "docs",
       "output": "docs/<Project>-Documentation-Set.pdf",
       "structure": [
         {"part": "1. Requirements", "docs": [
           {"num":"1","acr":"SRS","file":"SRS.md","title":"...","landscape":false}
         ]}
       ]
     }
   (A `file` ending in .pdf is concatenated as a pre-rendered leaf; `../` may reach
   outside docs_dir; any key starting with `_` is ignored -- use `_notes` for
   rationale. Template: ~/.claude/commands/lib/DOCSET.example.json)
4. Add a thin build script at orchestrator/build_docset_pdf.py that locates the
   shared engine (env CLAUDE_COMMANDS_LIB -> ~/.claude/commands/lib -> the
   repo checkout, e.g. C:\.ai\.claude\commands\lib), then calls
   db.load_config('DOCSET.json') + db.build_docset(...). Keeping a .py entry point
   means /docs-review and /build-docs find and run it. (Model it on FRIS_NET's
   orchestrator/build_docset_pdf.py.)
5. Build it, then VERIFY: exit 0, output PDF timestamp advanced, sane page count,
   TOC entries present, and no `WARNING:` lines from the engine. Report those.

Do not copy the engine into this repo -- reference the shared one only.
````

Notes:
- If the project **already** has a combined PDF and its own build script, just run
  `/build-docs` (or `/docs-review`) — it finds and runs the existing script instead
  of duplicating setup.
- For a **one-off single file**:
  `python $HOME/.claude/commands/lib/docset_builder.py --single <in.md> <out.pdf> [--landscape]`
  (`$HOME` expands in both PowerShell and bash.)

---

### `/run-mode`

Launches the project's app in a requested run mode — `/run-mode <mode>`, or bare `/run-mode` for the documented default. (Formerly `/run`; renamed because Claude Code ships its own `run` skill, which hid this one.)

The skill carries no project knowledge of its own: a `RUN.md` in the project root is the source of truth, defining the available modes, each mode's launcher and arguments, the launch sequence, and any gates. If the project has no `RUN.md`, the skill offers to bootstrap one from what's actually in the repo (launch scripts, README, CI config) — verifying each mode before writing it down.

Pairs with `RUN.md` the same way `/handoff` pairs with `HANDOFF.md`.

---

### `/humanizer`

Reviews and edits text so it reads less like an LLM wrote it. The aim is better writing (specific, sourced, plainly structured), not detector evasion.

- `/humanizer <file or pasted text>` returns the full revised text, a change log grouped by level, and every `[ADD: ...]` placeholder the writer needs to fill.
- `/humanizer <file> review only` ranks the top tells with quoted snippets and suggested fixes, without rewriting.

It edits in priority order: substance, then structure, then phrasing, then typography. That order comes from the StoryScope study (Russell et al., COLM 2026), where editing AI stories to remove cliches and purple prose barely dented a detector built on narrative choices (95.5% to 93.9% macro-F1). It never invents facts, names, quotes or citations. Where the text needs one, it inserts a placeholder instead.

Everything it needs lives in [`skills/humanizer/`](skills/humanizer/) and is referenced by relative path, so the folder works wherever it is copied:

- `SKILL.md`: the instructions.
- `references/surface-patterns.txt`: sentence and formatting tells, paraphrased from Wikipedia's "Signs of AI writing", including what is *not* a reliable tell.
- `references/narrative-patterns.txt`: StoryScope's 30 core narrative features with human vs AI rates, per-model fingerprints, and nonfiction analogs.
- `scripts/scan.py`: a standard-library regex scanner (`python scan.py FILE [--json]`, `-` for stdin) that reports hits by category with line numbers and a weighted density band. Hits are leads, not verdicts.

---

## License

MIT — see [LICENSE](LICENSE).
