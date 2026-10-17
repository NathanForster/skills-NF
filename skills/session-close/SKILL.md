---
name: session-close
description: End-of-session checklist for ICM-governed projects. Validates requirements, adds tests, builds and tests, audits the docs, updates the handoff, then commits and pushes. Use when wrapping up a work session on such a project.
---

# Session Close

This skill drives three others: icm-validate, docs-review and handoff. They are
installed as sibling folders, so each one's instructions are at
`../<name>/SKILL.md` relative to this file. Read and follow them where the steps
below say so.

Runs the standard end-of-session checklist for any ICM-governed project (and
DoD projects that also maintain a DID documentation suite):

1. **ICM validation** — audit every requirement against source code and pipeline
   artifacts, advance statuses, fill gaps where possible.
1b. **Register ↔ traceability drift check** — cross-check the working tracker
   against the traceability spine and reconcile any contradiction.
2. **Additional tests** — identify untested pure functions and add coverage.
3. **Build & test** — build and test with the project's standard commands; fix
   any failures before continuing.
4. **Docs audit** — follow the docs-review skill over the documentation folder (detailed
   review, cross-reference checks, backfill, composite PDF rebuild). Skip this
   step entirely for projects without a `docs/` or `documentation/` folder.
5. **Handoff** — follow the handoff skill in end mode to update `HANDOFF.md` and produce the
   session summary (without its own commit — Step 6 handles that).
6. **Commit & push** — stage everything, commit once with a descriptive message,
   push the current branch.

---

## Step 1 — ICM Validation

Read and follow the full process in the [icm-validate skill](../icm-validate/SKILL.md), including its **findings-table
confirmation gate**: present the findings table and get user confirmation before
writing to the register or matrix.

- Read `requirements/workflows/03-baseline/requirements-register.md` in full.
- For every `Baselined` or `Implemented` row:
  - Check whether code exists in `src/`.
  - Check whether `source-development/workflows/03-implementation/input_<REQ-ID>_implementation.md` exists.
  - Check whether `source-development/workflows/04-validation/input_<REQ-ID>_validation.md` exists.
- Produce a findings table (REQ ID | Title | Current Status | Code | Impl artifact | Val artifact | New Status).
- On confirmation, update the register and `requirements/workflows/04-trace/traceability-matrix.md`:
  - Advance `Baselined` → `Implemented` where code is confirmed present.
  - Append `(backfill needed)` to Trace cells that are missing ICM artifacts.
  - Do NOT mark anything `Verified` without an explicit passing test or explicit user confirmation.
- Update the `Updated:` datestamp in both files (today's date; check it with `Get-Date` or `date` if unsure).

---

## Step 1b — Register ↔ traceability drift check

The requirements register is the working tracker and moves first. The traceability
matrix (RTVM) is the spine and is usually what ships in the documentation set — so
when they disagree, **it is the shipped document that is wrong**. Statuses are
updated in one place and not the other far more often than anyone expects.

Run the project's drift checker if it has one; on FRIS_NET:

```
python orchestrator/check_register_rtvm_drift.py
```

Reconcile every contradiction it reports, then re-run until clean. Where a project
has no checker, do the comparison by script rather than by eye — 300+ rows is well
past reliable manual review.

**Three traps to respect — each one produced a wrong conclusion before it was
understood (FRIS_NET s63):**

- **Compare the right columns.** An RTVM `Status` column may hold the requirement's
  *approval* state (e.g. `Approved` on 300 of 335 rows), not its implementation
  state; the verification *outcome* lives in `Result`. Check the value distribution
  before believing any mismatch — if one value dominates, it is the norm, not drift.
- **Not every mismatch is drift.** Register `Implemented` + RTVM `Pending` means
  *implemented, verification pending* — consistent, and "fixing" it makes an
  accurate row inaccurate.
- **A row may cover several REQ-IDs.** Key on every ID in the cell, or the trailing
  ones read as missing from the matrix.

**The class that matters most is a spine claiming work is NOT done when the register
records it complete** — that understates delivery in a shipped deliverable. On
FRIS_NET this hid five such rows, two carrying commit hashes, and they were found by
accident rather than by process. That is why this step exists.

---

## Step 1c — Propagation check: does the shipped document know?

Step 1b compares two trackers to each other. This step asks a different question:
**did the work reach the document that ships?** They fail independently, and the
second one has no checker on most projects.

On FRIS_NET:

```
python orchestrator/check_gate_propagation.py --selftest
python orchestrator/check_gate_propagation.py
```

The `--selftest` runs first and on purpose: it exercises the rule against synthetic
input in **both** states — a gate absent entirely must FIRE, one mentioned only in
prose must stay quiet — and exits non-zero if either is wrong. **If the selftest
fails, the checker's verdict is worthless, so read it before the run below.**

Then regenerate every generated document and ask git whether anything moved:

```
python orchestrator/build_rtvm_summary.py
python orchestrator/build_live_summary.py
python orchestrator/build_deviations_summary.py
git status --porcelain docs/
```

**A generated file that changes here was STALE IN THE LAST COMMIT** — the source
was edited and the summary never rebuilt, so the delivered document has been wrong
since then. That is a finding, not housekeeping: commit the regenerated file and say
what it had been missing.

**Why this step exists.** Three times in three sessions on FRIS_NET, work was
recorded correctly upstream and never propagated downstream, and every one surfaced
by accident rather than by process:

- **s78** — REQ-360..368 were in the register and absent from the RTVM entirely.
- **s80** — REQ-369..376 were in the RTVM but its generated SUMMARY had not been
  rebuilt since the previous close, so the shipped condensed matrix was missing eight
  requirements, five of them implemented and live-gated.
- **s80** — five driven live gates had no row in the checklist that IS the gate
  registry and the source of the shipped live summary.

The shape is always the same and always silent: **the upstream record is correct, so
nobody looking at it sees a problem.** Only the downstream reader is misled, and the
downstream reader is the customer.

**Two traps, both learned building the checker:**

- **Tune it before you trust it, then tune it no further.** Keyed on table rows alone
  the first version reported 25 gates, of which about 20 were fine — sweep GROUPS
  and DPI blocks documented in prose rather than one row each. A check that reports 25
  items with 20 false is a check nobody runs twice. Loosened to "mentioned anywhere in
  the registry" it reports 6, and they are real.
- **Range citations read as missing.** "closes LIVE-SU-002 through LIVE-SU-007" cites
  an endpoint that may have no row of its own. Confirm before backfilling one.

**Exercise it in the state it should FIRE in, not only today's state** (ICM §11).
A propagation checker that passes on a clean repo has proved nothing. `--selftest`
does this automatically now, and it was itself mutation-verified: break `is_known` to
return True and 2 of its 6 cases fail.

**⚠ AND ASSERT THAT THE MUTATION LANDED.** The first attempt at that mutation
printed "mutation applied", changed nothing, and the selftest passed — which reads
exactly like a detector that cannot detect. An unasserted string replace that silently
matches nothing is the same silent-no-op class as the resume check that skipped every
device and reported success. **A mutation test you did not prove was applied is not a
mutation test.**

---

## Step 2 — Additional Tests

- Read every source file that contains public pure functions (functions whose
  output depends only on arguments, not DB or UI state).
- Compare against the project's existing test suite to find gaps.
- Add new test methods (or new test classes) for any untested functions that can
  be tested without a live DB or running UI. Place them in the project's existing
  test project/directory, following its existing naming convention (typically one
  test class per source module).
- New tests must satisfy: no live SQL connection, no running UI, no real
  filesystem beyond a temp file that is cleaned up afterward.
- If a function cannot be tested without infrastructure (DB, serial port, network),
  add a comment `// [deferred — needs integration test harness]` (or the language's
  comment syntax) and move on.

---

## Step 3 — Build & Test

Use the project's standard build and test commands (e.g. `dotnet build` /
`dotnet test`, `npm run build` / `npm test`, `make`, etc. — detect from the repo).

- Fix every build error before proceeding.
- Fix every test failure before proceeding.
- Report: errors fixed, warnings noted, tests passed / failed.

---

## Step 4 — Docs Audit

**Skip this step if the project has no `docs/` (or `documentation/`) folder.**

Read and follow the [docs-review skill](../docs-review/SKILL.md). It performs the detailed per-document review,
cross-reference checks, update and backfill (behind its own findings-table
confirmation gate), and rebuilds the composite PDF if one exists.

**Assume full backfill is desired.** Fill every section that can now be
accurately stated from the available sources — not just a minimal or
highest-priority subset. The priority order below governs the *sequence* of
work, not its scope. The no-fabrication rule still applies: where information
genuinely does not exist yet, leave a scoped `[TBD — requires <input>]` rather
than inventing content.

When the suite is a DoD **Data Item Description (DID)** set — the MIL-STD-498
documentation artifacts, indicated by a `docs/GUIDE.md` listing them — apply
this DID-specific guidance on top of docs-review:

- Read `docs/GUIDE.md` first — it is the single source of truth for which
  documents exist, their dependency order, and which documents feed which others.
- Feed the review two extra sources beyond the codebase: the requirements
  register and traceability matrix (from Step 1), and the build/test results
  from Step 3 (for STR and RTVM verification status).
- Backfill in priority order — highest leverage first:
  - RTVM (feeds STR and is the spine of all traceability)
  - STR (test results are now knowable from the test run)
  - SDD (design is now largely knowable from the source)
  - SRS (requirements are baselined and stable)
  - SVD (version info is knowable from git log)
  - Remaining documents as time permits.
- The RTVM is the spine: all requirement UIDs must match those in the SRS/IRS.
  Cross-check identifiers before writing verification status into the RTVM or STR.

---

## Step 5 — Handoff

Read and follow the [handoff skill](../handoff/SKILL.md) in **end** mode to update
`HANDOFF.md` and produce the session summary.
Do **not** let handoff run its own commit/push — Step 6 makes a single commit
that includes `HANDOFF.md` along with everything else.

---

## Step 6 — Commit & Push

Review the working tree first and flag anything unexpected — files unrelated to
this session's work should be surfaced to the user before staging, not swept in
silently:

```sh
git status --short
```

Then stage all modified files (including `HANDOFF.md` from Step 5):

```sh
git add -A
```

Commit once with a message that summarises what changed (req statuses, test count,
DID sections filled):

```
docs: session-close — <short summary>

- ICM: <N> reqs advanced, <M> artifacts backfilled
- Tests: <K> new tests added, <total> total passing
- DIDs: <list of documents updated and sections filled>
- Build: 0 errors
```

Then push the current branch:

```sh
git push origin HEAD
```

---

## Notes

- Run steps in order. Do not commit/push (Step 6) until build and tests pass (Step 3).
- `Superseded` requirements: skip in all steps.
- If any source file has no register entry, flag it for the user — do not
  silently create REQ IDs.
- The docs audit is "best effort" — fill only what can be accurately stated.
  A well-scoped `[TBD]` is better than a plausible fabrication.
