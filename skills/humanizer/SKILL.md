---
name: humanizer
description: Review and edit text so it reads less like an LLM wrote it, fixing substance and structure before phrasing. Use when asked to humanize a draft, make writing sound less AI-generated, remove AI tells or chatbot leftovers, or review a document, essay, report or story for AI-typical patterns. Never invents facts; marks missing specifics with placeholders.
argument-hint: '[file path or pasted text] [optional: "review only"]'
---

# Humanizer

The input is what the user typed after the skill name, or the text they asked
you to work on. In Claude Code it may be appended at the end of these
instructions as `ARGUMENTS: ...`.

Paths below are relative to this skill's folder, the one containing this
`SKILL.md`.

The goal is better writing: specific, sourced, plainly structured prose that a
reader trusts. It is not detector evasion. Edits that only make text harder to
classify, without making it better, are out of scope, and so is any request to
disguise AI use where disclosure is required.

## Reading the input

- If the input ends with "review only" (any capitalization), strip those words
  and run in review-only mode (see below).
- If what remains is empty, ask the user for the text or a file path, and stop
  until they answer.
- If it is the path of a file that exists, read the whole file. Work on a copy
  of the text; do not overwrite the original unless the user asks.
- Otherwise treat it as pasted text. If it runs past a couple of short
  paragraphs, save it to a temp file (the session scratchpad if there is one,
  otherwise the system temp directory) so the scanner can read it. Short text
  can be piped to the scanner on stdin with `-` as the file name.

## Two facts that set the order of work

**(a) Surface edits alone are weak.** StoryScope (Russell et al., COLM 2026)
edited AI-written stories to remove cliches, redundant exposition and purple
prose, then re-ran a detector built on narrative choices. Detection fell only
from 95.5% to 93.9% macro-F1. The choices that mark text as AI-typical sit
mostly in what it says and how it is built, not in its sentences. So edit
substance and structure first, and phrasing after.

**(b) The most human signals cannot be invented.** Named sources, specific
facts, real names, dates and numbers are what make prose read as written by
someone who knows something. You can only use the ones that are true. When the
text needs one and it is not in the draft, insert a placeholder the writer can
fill, such as `[ADD: which report? year?]`. Never fabricate a fact, quote,
citation, name or statistic, however plausible, because a confident invented
specific is worse than the vague sentence it replaced.

## Workflow

### 1. Classify the genre

The genre decides which reference to read, because the two sources studied
different things.

- **Expository or business text** (reports, articles, proposals, emails,
  documentation, essays): read
  [references/surface-patterns.txt](references/surface-patterns.txt). For
  essays, proposals and reports, also skim section 5 ("Nonfiction analogs") of
  [references/narrative-patterns.txt](references/narrative-patterns.txt).
- **Fiction**: read
  [references/narrative-patterns.txt](references/narrative-patterns.txt)
  first, then [references/surface-patterns.txt](references/surface-patterns.txt).
  In fiction the structural tells matter most, per fact (a).
- **Chatbot leftovers** in any genre ("I hope this helps!", "Certainly!",
  offers of further help, render artifacts such as `contentReference[oaicite:0]`,
  unfilled template brackets) are deleted outright. They are not content, so
  there is nothing to rewrite.

### 2. Scan, then read

Run the bundled scanner, [scripts/scan.py](scripts/scan.py), with Python 3
(standard library only, nothing to install):

```
python "${CLAUDE_SKILL_DIR}/scripts/scan.py" FILE
```

If that path still starts with a `${` placeholder when you read it, replace
the placeholder with this skill's folder (the one containing this
`SKILL.md`). Use `-` as FILE to read from stdin, and add `--json` for
machine-readable output.

Treat each hit as a lead, not a verdict. A single "crucial" means nothing.
What matters is density, and clusters of different kinds of hit in the same
passage. Use the scan to decide where to look first.

Then read the whole text yourself for what regex cannot see: whether claims
are sourced, whether the structure is a formula, whether the specifics are
real, whether the ending tells the reader what to think. In fiction, the
narrative patterns are almost entirely invisible to the scanner.

### 3. Edit in priority order

Work top down. A later level is wasted effort if an earlier one will delete
the sentence anyway.

**Substance.** What the text claims and on what basis.
- Cut significance inflation: "stands as a testament to", "marks a pivotal
  moment", "reflects broader trends". Keep the specific fact; delete the rating
  attached to it.
- Name the source for any claim that needs one, or mark
  `[ADD: who says this? cite one]`. Replace "experts argue" with the expert, or
  cut the claim.
- Delete trailing -ing editorializing clauses (", highlighting its enduring
  value."). They are unsourced interpretation bolted onto a fact, and the
  sentence almost always stands better without them.
- Replace promotional description with plain description: what the thing is,
  where, how big, since when.
- In fiction, apply the moves in `narrative-patterns.txt` section 3: remove
  the narrator's stated lesson, name an emotion instead of staging it in the
  body, loosen the causal chain, let the ending stay partly open.

**Structure.** How the text is built.
- Remove the "despite its strengths, X faces several challenges ... future
  prospects" formula. If the challenges are real, name them with specifics.
- Delete restating summaries: "In conclusion", "Overall", paragraphs that end
  by repeating their opening.
- Turn bold-header bullet lists (`- **Label:** text`) into prose where the
  items are argument, or into a plain list or table where they are data.
- Give every heading its own content, and vary section and paragraph length by
  importance rather than making every block the same shape.

**Phrasing.** Sentence-level habits.
- Restore plain is, are and has in place of "serves as", "stands as",
  "boasts", "features", "offers".
- Break reflexive triplets. Keep the items that carry distinct information;
  two is often the honest number.
- Rewrite "not just X, but Y" and "it's not X, it's Y" as one direct
  statement of what the thing is.
- Swap AI-vocabulary words for the plain word the sentence needs, one at a
  time, choosing by meaning. Often the best replacement is nothing.

**Typography.** Last, because it matters least.
- Replace most em dashes with a comma, colon, parentheses or full stop. Keep
  one only where the interruption is genuinely abrupt.
- Remove excess bold and all decorative emoji.
- Use sentence-case headings.
- Make quote marks consistent with the house style; do not change their style
  just to look less AI-typical.

### 4. Guard against overcorrection

Overcorrected text is its own tell, and it is worse writing. Check the
revision against these before delivering it.

- Leave alone the things Wikipedia's editors list as ineffective indicators:
  perfect grammar, formal register, transition words in moderation, curly
  quotes, and a mix of casual and formal registers. None of them reliably
  indicates AI, and "fixing" them damages good prose.
- Do not introduce new tells. Swapping every em dash for a semicolon, cycling
  synonyms so no word repeats, or replacing every "crucial" with the same
  substitute all create patterns of their own. Repeating a noun is normal.
- Do not inject fake casualness, slang, contractions the writer never uses, or
  deliberate typos. Those make text worse and read as staged.
- Preserve meaning, facts, citations, the writer's voice, and any required
  format (a style guide, a template, a citation standard, a word limit). When
  a fix would change meaning, flag it instead of making it.

### 5. Deliver

Give the user, in this order:

1. **The full revised text.** Complete, not a diff, so it can be used as is.
2. **A brief change log grouped by level** (substance, structure, phrasing,
   typography), naming the kinds of change and a representative example of
   each. Keep it short; the revision is the deliverable.
3. **Every `[ADD: ...]` placeholder**, listed with what it needs, so the writer
   can fill them before the text is used. Also list any `[VERIFY: ...]` flags
   for citations that look broken or fabricated. Re-running the scanner on the
   revision lists these under `writer_todos`, unscored, which is a quick check
   that none were missed.
4. **Optionally, one line on residual risk**: what still reads as AI-typical
   and why it was left, for example a formula the required template imposes.

## Review-only mode

Do not rewrite. Instead:

- Report the scanner's density score and band in one line.
- Rank the top tells, most consequential first. For each, quote the snippet
  (with its line number when working from a file), name the pattern, and give
  a concrete suggested fix.
- Rank substance and structure above phrasing and typography, for the reason
  in fact (a).
- Describe the text as "reads as AI-typical" or name the specific pattern.
  Never say it "was written by AI". Detectors and human readers are both often
  wrong, and the writer may simply write this way.

## Integrity

If the user mentions that AI use has to be disclosed (a class, a publisher, a
journal, an employer), note once and briefly that editing does not change the
disclosure obligation, then help with the writing.
