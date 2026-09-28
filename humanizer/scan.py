#!/usr/bin/env python3
"""Regex lead-finder for AI-typical writing patterns.

Usage:
    python scan.py FILE [--json]
    python scan.py -            (read from stdin)

Standard library only. Every hit is a LEAD, not a verdict. Single hits mean
little; clusters of different kinds of hits in the same passage mean more.
The weighted density score exists to rank passages for attention, not to
classify authorship.

Pattern sources: Wikipedia "Signs of AI writing" (surface tells) and
Russell et al., "StoryScope" (COLM 2026) for the reminder that surface edits
alone move detection very little.

All non-ASCII characters are written as escapes so this file stays pure ASCII
and behaves the same on any console encoding.
"""

import argparse
import bisect
import json
import re
import sys

# ---------------------------------------------------------------------------
# Scoring
#
# Weights reflect how hard a hit is to explain away, not how ugly it is.
# Render artifacts are machine output that no human types, so they dominate.
# Em dashes are common in good human prose, so they are discounted.
# mixed_quotes is reported but NOT scored: both sources say quote style alone
# is unreliable (Word, macOS, Chicago style and citation tools all produce
# curly quotes), and scoring it would push edits toward the exact
# overcorrection the command warns against.

WEIGHTS = {
    "render_artifacts": 5,
    "chatbot_leftovers": 3,
    "significance_inflation": 2,
    "participle_tails": 2,
    "negative_parallelism": 2,
    "notability_padding": 2,
    "em_dashes": 0.5,
}
DEFAULT_WEIGHT = 1
# writer_todos are the [ADD: ...] / [VERIFY: ...] markers the humanizer
# inserts on purpose. They are listed so none get missed, but not scored.
UNSCORED = {"mixed_quotes", "writer_todos"}

BAND_LOW = 8.0
BAND_HIGH = 20.0

# Below this length one hit is worth several points of density, so the report
# warns that the band is unstable.
SHORT_TEXT_WORDS = 300

# ---------------------------------------------------------------------------
# Patterns
#
# MULTILINE is applied to every category so that "^" anchors work where used.
# Inside multiline patterns use [ \t] rather than \s: \s matches newlines and
# would let a match run past the end of its line, which shifts the reported
# line number onto the wrong line.

PATTERNS = {
    "ai_vocabulary": [
        r"\badditionally\b",
        r"\balign(?:s|ed)? with\b",
        r"\bboast(?:s|ed|ing)?\b",
        r"\bbolster(?:s|ed|ing)?\b",
        r"\bcrucial\b",
        r"\bdeep dive\b",
        r"\bdelv(?:e|es|ed|ing)\b",
        r"\bemphasiz(?:e|es|ed|ing)\b",
        r"\benduring\b",
        r"\benhanc(?:e|es|ed|ing|ement)\b",
        r"\bfoster(?:s|ed|ing)\b",
        r"\bgarner(?:s|ed|ing)?\b",
        r"\bhighlight(?:s|ed|ing)?\b",
        r"\binterplay\b",
        r"\bintricate\b",
        r"\bintricacies\b",
        r"\blandscape\b",
        r"\bmeticulous(?:ly)?\b",
        r"\bpivotal\b",
        r"\brobust\b",
        r"\bshowcas(?:e|es|ed|ing)\b",
        r"\btapestry\b",
        r"\btestament\b",
        r"\bunderscor(?:e|es|ed|ing)\b",
        r"\bvaluable\b",
        r"\bvibrant\b",
        r"\bgroundbreaking\b",
        r"\brenowned\b",
        r"\bseamless(?:ly)?\b",
        r"\bprofound(?:ly)?\b",
        r"\bnestled\b",
        r"\bmultifaceted\b",
        r"\bmyriad\b",
        r"\bunwavering\b",
        r"\btransformative\b",
        r"\bholistic\b",
        r"\bsynergy\b",
        r"\bcutting-edge\b",
        r"\bever-(?:evolving|changing|growing)\b",
        r"\btreasure trove\b",
        r"\bharness(?:es|ed|ing)?\b",
        r"\bleverag(?:e|es|ed|ing)\b",
        # Grok-leaning "scientific" vocabulary
        r"\bempirical(?:ly)?\b",
        r"\bcorrelat(?:e|es|ed|ing|ion)\b",
    ],
    "significance_inflation": [
        r"\bstands as\b",
        r"\ba testament to\b",
        r"\b(?:is|was|serves as|stands as) a reminder\b",
        r"\bplay(?:s|ed|ing)? an? (?:crucial|pivotal|vital|significant|key|important|central) role\b",
        r"\ban? (?:crucial|pivotal|vital|significant|key) (?:role|moment|turning point|milestone)\b",
        r"\bunderscor(?:e|es|ed|ing) (?:its|the|their) (?:importance|significance|role)\b",
        r"\bhighlight(?:s|ed|ing)? (?:its|the|their) (?:importance|significance|enduring|lasting)\b",
        r"\breflect(?:s|ed|ing)? (?:a |the )?broader\b",
        r"\bsymboliz(?:es|ing) (?:its|the|their) (?:ongoing|enduring|lasting)\b",
        r"\bcontribut(?:es|ed|ing) to the broader\b",
        r"\bsetting the stage for\b",
        r"\bmark(?:s|ed|ing)? a (?:pivotal|significant|key|major|new) (?:moment|shift|milestone|chapter|era)\b",
        r"\brepresent(?:s|ed|ing)? a (?:significant |major |fundamental )?shift\b",
        r"\bkey turning point\b",
        r"\bevolving landscape\b",
        r"\bfocal point\b",
        r"\bindelible mark\b",
        r"\bdeeply rooted\b",
        r"\b(?:enduring|lasting|rich) (?:legacy|heritage|tradition|value)\b",
        r"\btransformative power\b",
        r"\bcement(?:s|ed|ing)? (?:its|their|his|her) (?:place|role|status|legacy|reputation)\b",
        r"\bsolidif(?:y|ies|ied|ying) (?:its|their|his|her) (?:role|place|status)\b",
        r"\bpart of a broader (?:movement|trend|effort|shift)\b",
        r"\bgenerat(?:ed|ing) (?:considerable |significant |renewed )?debate\b",
        r"\bspark(?:ed|ing) (?:considerable |renewed )?(?:debate|discussion|conversation|interest)\b",
        r"\bprompt(?:ed|ing) broader reflection\b",
        r"\brais(?:es|ed|ing) (?:profound |philosophical |important |broader )?questions about\b",
        r"\bshap(?:ed|ing) (?:emerging )?(?:policy )?discussions\b",
        r"\bcontinues to thrive\b",
        r"\bremains a (?:vital|crucial|key|central|defining)\b",
        r"\bplays a role in the ecosystem\b",
        r"\bin the evolution of\b",
        r"\bcornerstone of\b",
    ],
    "promotional_tone": [
        r"\bboasts a\b",
        r"\brich (?:cultural )?(?:heritage|history|tapestry|tradition)\b",
        r"\bnatural beauty\b",
        r"\bnestled (?:in|within|among|between|amid)\b",
        r"\bin the heart of\b",
        r"\bbreathtaking\b",
        r"\bstunning\b",
        r"\bpicturesque\b",
        r"\bcharming\b",
        r"\bbustling\b",
        r"\bthriving\b",
        r"\bmust-(?:visit|see|read)\b",
        r"\bworld-class\b",
        r"\bstate-of-the-art\b",
        r"\bpremier\b",
        r"\bunparalleled\b",
        r"\b(?:diverse|wide|vast) array\b",
        r"\bexemplif(?:y|ies|ied)\b",
        r"\bcommitment to (?:excellence|quality|sustainability|innovation|craftsmanship)\b",
        r"\bdedication to (?:craftsmanship|excellence|quality|innovation)\b",
        r"\bgateway to\b",
        r"\bscenic\b",
        r"\bglimpse into\b",
        r"\bvalue-driven\b",
        r"\bfascinating\b",
        r"\bworth (?:visiting|a visit)\b",
        r"\bvibrant (?:town|city|community|culture|hub)\b",
        r"\bhidden gem\b",
    ],
    "vague_attribution": [
        r"\bindustry reports\b",
        r"\bobservers have (?:cited|noted|argued|described|suggested)\b",
        r"\bexperts (?:argue|say|note|believe|suggest|agree|contend)\b",
        r"\bsome (?:critics|observers|scholars|experts|commentators) (?:argue|note|say|believe|have)\b",
        r"\bcritics have (?:argued|noted|described|praised|suggested)\b",
        r"\bseveral (?:sources|publications|outlets|scholars|studies|commentators)\b",
        r"\bmany (?:scholars|historians|researchers|critics|observers|commentators)\b",
        r"\bscholars (?:argue|note|have noted|generally|widely|agree)\b",
        r"\bresearchers (?:and conservationists|have noted|argue|believe|suggest)\b",
        r"\bdescribed in scholarship\b",
        r"\bmodern researchers treat\b",
        r"\baccording to (?:sources|reports|observers|some)\b",
        r"\bis widely (?:regarded|considered|interpreted|seen|believed|held|accepted|praised)\b",
        r"\bit is (?:widely|generally|often) (?:believed|held|accepted|thought|understood)\b",
        r"\bcommentators have\b",
        r"\banalysts (?:say|note|argue|believe|expect)\b",
        r"\bsources (?:identified|indicate|suggest|confirm|describe)\b",
        r"\breviewers (?:praised|noted|described|highlighted)\b",
        r"\b(?:publications|outlets|journals|magazines) such as\b",
        r"\bis often (?:cited|described|regarded|seen|considered)\b",
        r"\bare (?:widely|generally) (?:seen|viewed|regarded) as\b",
        r"\bhas been (?:widely |broadly )?(?:praised|criticized|described|recognized) (?:as|for|by)\b",
    ],
    "notability_padding": [
        r"\bindependent coverage\b",
        r"\b(?:local|regional|national|international) media outlets\b",
        r"\bmedia outlets\b",
        r"\b(?:music|business|tech|trade|toy industry|fashion) (?:outlets|publications|press)\b",
        r"\btrade publications\b",
        r"\b(?:cited|featured|profiled|mentioned|highlighted) in\b",
        r"\bwritten by a leading expert\b",
        r"\bactive social media presence\b",
        r"\bmaintains an? (?:strong |active |significant |growing )?(?:digital|social media|online) presence\b",
        r"\bwas identified by\b",
        r"\bwidely[- ]read outlets\b",
        r"\bhigh-quality,? (?:and )?independent\b",
        r"\brepeated national media coverage\b",
        r"\bsyndicated through\b",
        r"\bnot trivial mentions\b",
        r"\bregional press coverage\b",
        r"\bdocumented in archived\b",
        r"\bcoverage relating to\b",
        r"\b(?:secondary|substantial|sustained|verifiable) coverage\b",
        r"\bpeer-reviewed sources\b",
        r"\bongoing public presence\b",
        r"\bprominent media outlets\b",
    ],
    "copula_avoidance": [
        r"\bserves as\b",
        r"\bstands as\b",
        r"\bfunctions as\b",
        r"\boperates as\b",
        r"\bacts as (?:the|a|an)\b",
        r"\brepresents an?\b",
        r"\bmark(?:s|ed)? the\b",
        r"\brefers to\b",
        r"\bboasts\b",
        r"\bholds the distinction of\b",
        r"\bmaintains an?\b",
        r"\boffers an?\b",
        r"\bfeatures an?\b",
        r"\bis characterized by\b",
        r"\bbegan (?:his|her|their|its) career as\b",
        r"\bventured into\b",
        r"\bemerged as\b",
        r"\bposition(?:s|ed)? (?:it|them|itself|themselves) as\b",
    ],
    "participle_tails": [
        r",[ \t]*(?:highlighting|underscoring|emphasizing|reflecting|symbolizing|showcasing"
        r"|demonstrating|illustrating|cementing|solidifying|ensuring|contributing|cultivating"
        r"|fostering|encompassing|enhancing|marking|signaling|signalling|reinforcing|preserving"
        r"|accentuating|imparting|positioning|allowing|enabling|creating|providing|offering"
        r"|adding|furthering|making|leaving|helping|serving|bringing|paving)\b[^.!?\n]*",
    ],
    "negative_parallelism": [
        r"\bnot (?:only|just|merely|simply)\b[^.!?\n]{0,140}\bbut\b",
        r"\b(?:is|was|are|were)n['\u2019]?t (?:just|only|merely|simply)\b",
        r"\b(?:do|does|did)n['\u2019]?t (?:just|only|merely|simply)\b",
        r"\bit['\u2019]s not\b[^.!?\n]{0,100},[ \t]*it['\u2019]s\b",
        r"\bno\b[^.!?\n]{0,50},[ \t]*no\b[^.!?\n]{0,50},[ \t]*just\b",
        # "Y rather than X" as a comma-led participle clause, the Grok-typical
        # form (", prioritizing A rather than B"). Plain "A rather than B" is
        # ordinary English and is often a writer's hedge, so it is not flagged.
        r",[ \t]*\w+ing\b[^.!?\n]{0,100}\brather than\b",
        r"\bnot because\b[^.!?\n]{0,90}\bbut because\b",
    ],
    "formulaic_structure": [
        r"\bdespite (?:its|their|these|the|his|her)\b[^.!?\n]{0,120}"
        r"\b(?:challenges|strengths|success|promise|popularity|limitations|prosperity)\b",
        r"\bface(?:s|d)? (?:several|numerous|many|a number of|various|significant|new) "
        r"(?:challenges|obstacles|hurdles|limitations)\b",
        r"\bdespite these challenges\b",
        r"\bchallenges and (?:legacy|opportunities|future|prospects|limitations|directions)\b",
        r"\bfuture (?:outlook|prospects|directions|challenges)\b",
        r"\bin (?:conclusion|summary)\b",
        r"^[ \t]*overall,",
        r"\bit(?:['\u2019]s| is) (?:important|worth|critical|crucial|essential) to "
        r"(?:note|remember|consider|recognize)\b",
        r"\bworth noting\b",
        r"\bawards and recognition\b",
        r"\blooking ahead\b",
        r"\bcontinues to evolve\b",
        r"\bkey (?:takeaways|highlights)\b",
        r"\bin this (?:article|section|report|paper), we (?:will )?(?:explore|discuss|examine|look)\b",
        r"\bmay vary\b",
        r"\bthis section would\b",
    ],
    # Deliberately broad: three-item lists are ordinary English too. Treated as
    # candidates to eyeball, which is why the category is named that way.
    "rule_of_three_candidates": [
        r"\b[A-Za-z][A-Za-z-]{3,}, [A-Za-z][A-Za-z-]{3,},? and [A-Za-z][A-Za-z-]{3,}\b",
    ],
    "chatbot_leftovers": [
        r"\bI hope this helps\b",
        r"\bhope (?:this|that) helps\b",
        r"Of course!",
        r"Certainly!",
        r"\bYou(?:['\u2019]re| are) absolutely right\b",
        r"\bWould you like\b",
        r"\bis there anything else\b",
        r"\blet me know if\b",
        r"\bLet me know your thoughts\b",
        r"\bmore detailed breakdown\b",
        r"^[ \t]*Here(?:['\u2019]s| is) (?:a|the|your)\b",
        r"\bfeel free to (?:ask|let me|reach|modify|adjust)\b",
        r"\bas an AI language model\b",
        r"\bas a large language model\b",
        r"\bI cannot (?:offer|provide) (?:medical|legal|financial)\b",
        r"\b(?:Up to|As of) my last (?:training|knowledge) update\b",
        r"\bI hope this message finds you well\b",
        r"\byou can copy and paste\b",
        r"\bhappy to (?:help|revise|adjust|expand)\b",
        r"\bwhile specific details (?:are|remain) (?:limited|scarce)\b",
        r"\bnot widely (?:available|documented|disclosed)\b",
        r"\bbased on available information\b",
        r"\bin the (?:provided|available) (?:sources|search results)\b",
        r"\bmaintains a low profile\b",
        r"\bkeeps personal details private\b",
    ],
    "render_artifacts": [
        r"contentReference",
        r"oaicite",
        r"oai_citation",
        r"turn\d+search\d+",
        r"attributableIndex",
        r"\[cite:[ \t]*\d+",
        r"\[span_\d+\]\(start_span\)",
        r"grok[_-]card",
        r"grok_render_citation_card_json",
        r"\u3010\d+\u2020[^\u3011]*\u3011",
        r"\[attached_file:\d+\]",
        r"\[web:\d+\]",
        r"ppl-ai-file-upload",
        r"utm_source=(?:chatgpt\.com|openai|copilot\.com)",
        r"referrer=grok\.com",
        r":::writing\{variant=",
    ],
    # Unfilled template brackets left by a chatbot. The humanizer's own
    # [ADD: ...] and [VERIFY: ...] markers are excluded here and counted under
    # writer_todos instead, so a revised draft is not penalized for them.
    "placeholders": [
        r"\[(?!(?:ADD|VERIFY):)[^\]\n]{0,100}?\b(?:insert|describe|specific|your|placeholder"
        r"|link to|name of|e\.g\.|TBD|TODO)\b[^\]\n]{0,100}?\](?!\()",
        r"\[NUMBER\]",
        r"\bLorem ipsum\b",
        r"\bTODO\b",
        r"\bXXXX+\b",
    ],
    "writer_todos": [
        r"\[(?:ADD|VERIFY):[^\]\n]*\]",
    ],
    "em_dashes": [
        r"\u2014",
    ],
    "bold_list_headers": [
        # "- **Label:** text" and "- **Label**: text"
        r"^[ \t]*(?:[-*+\u2022\u2023\u25cf\u2013]|\d+[.)])[ \t]*\*\*[^*\n]+?(?::\*\*|\*\*:)",
    ],
    "bold_spans": [
        r"\*\*[^*\n]+?\*\*",
    ],
    "emoji": [
        r"[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF"
        r"\u2600-\u27bf\u2b00-\u2bff\ufe0f\u2190-\u21ff\u2900-\u297f]",
    ],
}

SMALL_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "nor", "of", "off", "on", "or", "per", "the", "to", "up", "via", "with",
    "over", "than", "that", "vs", "v", "is", "are", "be",
}

HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
WORD_RE = re.compile(r"[A-Za-z0-9'\u2019\u2011-]+")


# ---------------------------------------------------------------------------

def line_index(text):
    """Offsets at which each line starts, for mapping match positions to lines."""
    starts = [0]
    for m in re.finditer(r"\n", text):
        starts.append(m.end())
    return starts


def line_of(starts, pos):
    return bisect.bisect_right(starts, pos)


def norm(s):
    """Collapse a match to a comparable key for grouping."""
    return re.sub(r"\s+", " ", s.strip()).lower()


def find_regex_hits(text, starts):
    """Run every compiled pattern. Returns {category: [(line, matched_text)]}.

    Within one category, overlapping matches count once: "plays a vital role"
    and "a vital role" are a single tell, and counting both would inflate the
    score. The longest match wins. Overlap ACROSS categories is kept on
    purpose, because one phrase can be two different habits at once.
    """
    out = {}
    for cat, pats in PATTERNS.items():
        spans = []
        for pat in pats:
            for m in re.finditer(pat, text, re.IGNORECASE | re.MULTILINE):
                if m.group(0).strip():
                    spans.append((m.start(), m.end()))
        kept = []
        for start, end in sorted(spans, key=lambda s: (-(s[1] - s[0]), s[0])):
            if all(end <= ks or start >= ke for ks, ke in kept):
                kept.append((start, end))
        hits = []
        for start, end in sorted(kept):
            matched = text[start:end]
            # Keep reported snippets short so the report stays readable.
            snippet = matched if len(matched) <= 90 else matched[:87] + "..."
            hits.append((line_of(starts, start), snippet))
        if hits:
            out[cat] = hits
    return out


def find_title_case_headings(text, starts):
    """Markdown headings whose significant words are all capitalized."""
    hits = []
    for m in HEADING_RE.finditer(text):
        heading = m.group(2).strip()
        # Ignore inline markup and links when judging capitalization.
        plain = re.sub(r"[*_`\[\]()#]", " ", heading)
        words = [w for w in plain.split() if re.search(r"[A-Za-z]", w)]
        if len(words) < 2:
            continue
        significant = [w for w in words if w.lower().strip(".,:;") not in SMALL_WORDS]
        if len(significant) < 2:
            continue
        if all(w[0].isupper() for w in significant if w[0].isalpha()):
            hits.append((line_of(starts, m.start()), heading[:90]))
    return hits


def find_quote_mix(text, starts):
    """Report quote-style inconsistency. Reported, never scored."""
    counts = {
        "straight_double": text.count('"'),
        "curly_double": text.count("\u201c") + text.count("\u201d"),
        "straight_apostrophe": text.count("'"),
        "curly_apostrophe": text.count("\u2019"),
    }
    hits = []
    if counts["straight_double"] and counts["curly_double"]:
        hits.append((0, "mixed double quotes: straight %d, curly %d"
                     % (counts["straight_double"], counts["curly_double"])))
    if counts["straight_apostrophe"] and counts["curly_apostrophe"]:
        hits.append((0, "mixed apostrophes: straight %d, curly %d"
                     % (counts["straight_apostrophe"], counts["curly_apostrophe"])))
    return hits, counts


def em_dash_spacing(text):
    spaced = len(re.findall(r"[ \t]\u2014[ \t]", text))
    total = text.count("\u2014")
    return spaced, total


def group(hits):
    """Group (line, text) hits by distinct match text."""
    groups = {}
    for line, snippet in hits:
        key = norm(snippet)
        entry = groups.setdefault(key, {"text": snippet, "lines": []})
        entry["lines"].append(line)
    ordered = sorted(groups.values(), key=lambda g: (-len(g["lines"]), g["text"]))
    for g in ordered:
        g["lines"].sort()
    return ordered


def analyze(text):
    starts = line_index(text)
    words = len(WORD_RE.findall(text))
    per_k = (words / 1000.0) if words else 0.0

    found = find_regex_hits(text, starts)

    tc = find_title_case_headings(text, starts)
    if tc:
        found["title_case_headings"] = tc

    qmix, qcounts = find_quote_mix(text, starts)
    if qmix:
        found["mixed_quotes"] = qmix

    categories = {}
    weighted = 0.0
    for cat, hits in found.items():
        count = len(hits)
        weight = WEIGHTS.get(cat, DEFAULT_WEIGHT)
        scored = cat not in UNSCORED
        if scored:
            weighted += weight * count
        categories[cat] = {
            "count": count,
            "per_1000_words": round(count / per_k, 2) if per_k else 0.0,
            "weight": weight if scored else 0,
            "scored": scored,
            "groups": group(hits),
        }

    density = (weighted / per_k) if per_k else 0.0
    band = "low" if density < BAND_LOW else ("moderate" if density <= BAND_HIGH else "high")

    spaced, total_dashes = em_dash_spacing(text)

    return {
        "words": words,
        "categories": categories,
        "weighted_hits": round(weighted, 2),
        "density_per_1000_words": round(density, 2),
        "band": band,
        "bands": {"low": "< %g" % BAND_LOW, "moderate": "%g to %g" % (BAND_LOW, BAND_HIGH),
                  "high": "> %g" % BAND_HIGH},
        "quote_counts": qcounts,
        "em_dash_spaced": spaced,
        "em_dash_total": total_dashes,
        "note": "Density is a lead, not a verdict.",
    }


def fmt_lines(lines, limit=12):
    shown = lines[:limit]
    text = ", ".join("L%d" % n if n else "file" for n in shown)
    if len(lines) > limit:
        text += ", +%d more" % (len(lines) - limit)
    return text


def report(res, path):
    w = sys.stdout.write
    w("AI-writing pattern scan: %s\n" % path)
    w("Words: %d\n\n" % res["words"])

    if not res["categories"]:
        w("No pattern hits.\n\n")
    else:
        order = sorted(
            res["categories"].items(),
            key=lambda kv: (-(kv[1]["weight"] * kv[1]["count"]), kv[0]),
        )
        w("%-26s %6s %9s %7s\n" % ("CATEGORY", "HITS", "PER 1K", "WEIGHT"))
        w("%s\n" % ("-" * 52))
        for cat, data in order:
            w("%-26s %6d %9.2f %7s\n" % (
                cat, data["count"], data["per_1000_words"],
                data["weight"] if data["scored"] else "n/s"))
        w("\n")
        for cat, data in order:
            tag = "" if data["scored"] else "  (reported, not scored)"
            w("%s  [%d hits]%s\n" % (cat, data["count"], tag))
            for g in data["groups"]:
                w("    %-56s %s\n" % (repr(g["text"])[:56], fmt_lines(g["lines"])))
            w("\n")

    if res["em_dash_total"]:
        w("Em dashes: %d total, %d with spaces around them.\n"
          % (res["em_dash_total"], res["em_dash_spaced"]))
        w("  Spaced em dashes are the more AI-typical habit.\n\n")

    w("Weighted hits: %.2f\n" % res["weighted_hits"])
    w("Density: %.2f per 1,000 words  ->  %s\n"
      % (res["density_per_1000_words"], res["band"].upper()))
    w("  bands: low %s | moderate %s | high %s\n" % (
        res["bands"]["low"], res["bands"]["moderate"], res["bands"]["high"]))
    if 0 < res["words"] < SHORT_TEXT_WORDS:
        w("  Short text (%d words): a single hit can move the band. Weigh the\n"
          "  individual hits above rather than the score.\n" % res["words"])
    w("\n")
    w("Density is a lead, not a verdict. Regex cannot see whether a claim is\n")
    w("sourced, whether a structure is formulaic, or whether the substance is\n")
    w("specific. Read the text; treat clusters as places to look first.\n")


def main():
    ap = argparse.ArgumentParser(
        description="Flag AI-typical writing patterns in a text file.")
    ap.add_argument("file", help='path to scan, or "-" for stdin')
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="emit machine-readable JSON instead of a report")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if args.file == "-":
        data = sys.stdin.buffer.read()
        text = data.decode("utf-8", errors="replace")
        label = "<stdin>"
    else:
        try:
            with open(args.file, "rb") as fh:
                text = fh.read().decode("utf-8", errors="replace")
        except OSError as exc:
            sys.stderr.write("cannot read %s: %s\n" % (args.file, exc))
            return 2
        label = args.file

    res = analyze(text)
    if args.as_json:
        res["file"] = label
        sys.stdout.write(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    else:
        report(res, label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
