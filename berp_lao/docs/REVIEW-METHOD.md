# REVIEW-METHOD — how work on this repository is accepted

**Date:** 2026-09-16
**Status:** Active. Amend by adding, not by rewriting history.

This file records *how* claims about this codebase are established, not what the
codebase does. It exists because a green test suite once certified a broken PDF.

---

## The principles

**P1 — the instrument must point outward.**

> **Tests derived solely from an ADR can prove conformance to a false
> architectural assumption. At least one acceptance instrument must interrogate
> the external system whose behaviour the ADR claims to describe.**

**P2 — the instrument must itself be trusted before its answer is.**

> **A negative diagnostic result is not trustworthy until the diagnostic
> mechanism itself has been validated against a known-good system.**

Both complement the rule already in use elsewhere in bERP: **ask each instrument
its own question.**

P1 says: do not let the map audit the map. P2 says: before believing the
compass, point it at north.

---

## Incident 1 — the green suite that certified a broken PDF (produced P1)

**2026-09-16, ADR-A4 (Lao fonts).**

ADR-A4 correctly identified that the Lao Tax Invoice loaded no Lao font. It then
specified the fix as *declare `@font-face` in the Print Format's `css` field*.
That specification was wrong.

What happened next is the part worth keeping:

```
ADR written
    ↓
implementation matches the ADR
    ↓
tests derived from the ADR
    ↓
82 tests green
    ↓
PDF still broken
```

The tests asserted that the print format declared `@font-face` — which it did.
They could not fail, because they were asking the implementation whether it had
obeyed the specification, and the specification was the thing that was wrong.

Rendering an actual PDF showed the inverse of the ADR's claim: on this rendering
stack `@font-face` **overrode** the fontconfig lookup, then failed, and the Lao
text did not survive. The correct mechanism was the one the ADR had dismissed.

**No amount of additional unit testing would have found this.** The missing layer
was an instrument pointed outward.

---

## Incident 2 — the diagnostic that reported four installed fonts as missing (produced P2)

**2026-09-16, `scripts/install-lao-fonts.sh`.**

The font installer ended with a verification loop. It reported all four required
faces `MISSING` on a machine where all four were installed and where
`fc-list | grep Phetsarath` printed matches when run by hand.

The verification was written as:

```bash
set -euo pipefail
...
if fc-list "$family:style=$style" | grep -q "$family"; then
```

The causal chain:

```
grep -q exits as soon as it finds its first match
    ↓
fc-list is still writing; its write hits a closed pipe
    ↓
fc-list dies on SIGPIPE → exit status 141
    ↓
set -o pipefail makes the pipeline's status the rightmost non-zero one
    ↓
the pipeline is non-zero even though grep succeeded
    ↓
the installed font is reported MISSING
```

Every element was doing its job. `pipefail` is correct practice. `grep -q`
short-circuiting is correct practice. Composed, they manufacture a false
negative — and, being a race between two processes, an *intermittent* one.

What makes this a governance incident rather than a shell bug is the sequence
that would have followed if it had not been caught:

```
diagnostic says MISSING
    ↓
"the install step is broken" — investigate the installer
    ↓
installer is fine, so investigate fontconfig
    ↓
fontconfig is fine, so investigate the font files
    ↓
hours spent debugging a system that was already correct
```

The defect was in the observer, not in the observed. Every hour after the first
would have been spent auditing something that was working.

**The fix applied.** Capture, then test — no pipeline, so no pipeline status to
misread:

```bash
found="$(fc-list "$family:style=$style" --format '%{file}\n' 2>/dev/null || true)"
if [ -n "$found" ]; then ...
```

**The alternative that looked stronger.** `fc-list` answers "is this face in the
index?". The question the renderer actually asks is "what face do I get when I
request this family?" — which looks like `fc-match`:

```bash
fc-match "Phetsarath:style=Bold" --format '%{family}\n'
```

Asserting that `fc-match` *returns the requested family* rather than a substitute
looks like a closer invariant, because substitution is the exact failure mode
that produces plausible, wrong Lao.

> **This was implemented, then measured, and the claim did not survive. See
> Incident 3.** It is kept in the codebase as a support hint, not a verdict.

---

## Incident 3 — the replacement instrument that also over-claimed (P2, applied to itself)

**2026-09-16, `lao_regional/fonts.py`.**

Acting on Incident 2, an `fc-match` resolution probe was added beside the
`fc-list` presence check, on the reasoning above: *fc-match asks the renderer's
question, so its answer should be the verdict.* Two states were folded into one —
a substituted face reported `MISSING`, which would fail an install.

Then rule 8 was applied to the new instrument: run it against a known-bad system.
A strong-binding fontconfig rule was installed for the bench user —

```xml
<match target="pattern">
  <test name="family"><string>Phetsarath</string></test>
  <edit name="family" mode="assign" binding="strong"><string>DejaVu Sans</string></edit>
</match>
```

— and the three instruments were asked, in the same environment, same `HOME`:

```
fc-list  "Phetsarath:style=Bold"   →  /usr/local/share/fonts/berp-lao/Phetsarath-Bold.ttf
fc-match "Phetsarath:style=Bold"   →  DejaVu Sans
wkhtmltopdf, rendered PDF          →  Phetsarath-Regular   (pdffonts)
```

**The renderer ignored the substitution.** Qt WebKit does not take the same path
through fontconfig that `fc-match` does. The premise the new probe was built on —
*fc-match asks the renderer's question* — was false, in the same way ADR-A4's
premise had been false, one layer further out.

Had it shipped as designed, it would have failed installs on machines whose PDFs
were correct. A false negative, produced by a check written **specifically to
prevent false negatives.**

**What it is now.** Presence remains the verdict. Resolution is reported beside
it under its own vocabulary — `READY` / `SUBSTITUTED` / `UNKNOWN`, where
`SUBSTITUTED` is deliberately not `MISSING` — as a lead to follow if a PDF looks
wrong, and it fails nothing. The probe's own sentinel self-check survives, and
gates only the advisory reporting.

The instrument that genuinely answers the renderer's question is still the one
that renders a PDF and reads the fonts back out of it.

### Why this one is the most important of the three

Incidents 1 and 2 were mistakes. Incident 3 was a mistake **made while fixing
them, by someone who had just written the rule that catches it** — and the rule
caught it anyway, before it shipped, because it was applied mechanically rather
than only when suspicion was already present.

> **The method is worth more than the insight that produced it.** Anyone can be
> right about a failure after seeing it. The value is in running the check
> against the known-bad case every time, including — especially — on the
> instrument you just built to be the trustworthy one.

---

## The pattern all three incidents share

| # | The false thing | How it presented | What the instrument had encoded |
|---|---|---|---|
| 1 | False architectural assumption (`@font-face` is the mechanism) | 82 tests green against a broken PDF | The ADR's claim, restated as an assertion |
| 2 | False shell diagnostic (`fc-list \| grep -q` under `pipefail`) | Four installed fonts reported missing | A pipeline whose exit status does not mean what it appears to |
| 3 | False proxy for the consumer's question (`fc-match` as "what the renderer sees") | *Would have* failed installs whose PDFs were correct | A different subsystem's answer, mistaken for the renderer's |

> **Common failure mode: the observing instrument encoded the wrong behaviour,
> and then reported confidently.**

In case 1 the instrument was confidently green and the system was broken. In
case 2 the instrument was confidently red and the system was fine. The direction
of the error is incidental. What is not incidental is that in each case the
instrument was trusted on the strength of its premise rather than its
performance — and case 3 shows the premise can be wrong even when the person
writing it has just finished being burned by the same mistake.

Case 3 differs from the first two in exactly one respect, which is the whole
argument for keeping this document: **it never reached anyone**, because the
check was run before the claim was published.

A corollary worth stating plainly, because it is counter-intuitive: **a red
result deserves the same scepticism as a green one.** A failing check feels like
evidence of diligence, which is exactly why nobody audits it.

---

## The instrument ladder

Every non-trivial claim about behaviour should be placed on this ladder, and the
claim should not be stated more strongly than the rung that supports it.

| Rung | Instrument | The question it answers | What it cannot answer |
|---|---|---|---|
| 1 | Unit / structural test | Did we implement our declared rule? | Whether the rule is right |
| 2 | Integration test | Does the framework do what we think? | What a downstream tool does |
| 3 | **Renderer / external contract test** | **Does the external system actually behave as the ADR claims?** | Anything requiring human judgement |
| 4 | Artifact inspection | Did the intended thing reach the output? | Whether it is *correct* to a reader |
| 5 | Human visual acceptance | Is it right? | — |

Rung 3 is the one this repository was missing. `tests/test_renderer_contract.py`
is its first inhabitant: it launches the supported `wkhtmltopdf` binary, renders a
controlled Lao corpus, and asserts on the fonts actually embedded in the PDF.

`fc-list` and `fc-match` both sit on rung 2 — they interrogate *fontconfig*, not
the renderer — which is why neither can stand in for rung 3 and why Incident 3
happened when one of them was promoted.

### Worked example — the four questions for ADR-A4

```
Unit test            Did we implement our declared rule?
                     → the print format declares no @font-face

Integration test     Does Frappe's print pipeline carry our font-family?
                     → get_print_style writes it onto the print body

Renderer contract    Does wkhtmltopdf actually resolve the font?
                     → Phetsarath is embedded; DejaVu is not the Lao carrier

Artifact inspection  Did the intended font reach the PDF?
                     → pdffonts lists Phetsarath-Regular/Bold

Human verification   Did the Lao shape correctly?
                     → OPEN. BERP-LAO-VERIFY-001.
```

Four different instruments. Four different questions. Conflating any two of them
is how the original false green happened.

---

## Rules that follow

1. **An ADR that describes external behaviour must name the measurement.** Not
   "wkhtmltopdf ignores `@font-face`" but "measured on wkhtmltopdf 0.12.6, same
   HTML, only the `@font-face` block differing: …". State the scope of what was
   tested, and do not generalise past it.

2. **Scope normative claims to the supported stack.** The evidence shows what
   *this* rendering path does. It does not show what every build of the tool
   does, and the literature reports inconsistency across versions, formats and
   platforms — which is an additional argument for the constraint, not a
   weakening of it.

3. **Do not let a test's premise be its own evidence.** If a test only restates
   the ADR, it certifies nothing about the world.

4. **Distinguish "unknown" from "failed".** A check that cannot run has not
   found a defect. See `lao_regional/fonts.py`, where READY / MISSING / UNKNOWN
   are three states and UNKNOWN is never collapsed into MISSING.

5. **"It rendered characters" is not a success criterion.** For Lao specifically,
   a fallback font produces plausible-looking output with the combining marks in
   the wrong order. Correct-looking is not correct.

6. **Retain the artifact on failure.** A contract test that fails should leave
   the PDF behind for a human to open.

7. **Implement the risky ADR early, not last.** ADR-A4 was sequenced last because
   it looked like the largest piece of work. It was in fact the one whose stated
   design was wrong, and doing it first is what surfaced that. Prefer to
   front-load the decision that would be most expensive to discover was mistaken.

8. **Validate a diagnostic against a known-good system before believing it.**
   Run it once where the answer is known to be YES and once where it is known to
   be NO. A check that has only ever been run against the failing case has not
   been shown to distinguish the cases. This is P2, in operational form.

9. **Prefer the invariant whose question matches the consumer's — and prove the
   match rather than assuming it.** A probe that *sounds* like the consumer's
   question is not one. `fc-match` sounds like the renderer's question and is
   not; measured, the two disagree (Incident 3). Where a proxy cannot be shown
   to track the consumer, report it as evidence and let the consumer itself be
   the verdict.

10. **Treat a shell pipeline's exit status as a claim to be checked, not read.**
    Under `set -o pipefail`, a short-circuiting consumer (`grep -q`, `head`)
    makes its producer die on SIGPIPE and poisons the pipeline's status. Capture
    output into a variable, then test the variable.

---

## Test classification — correctness vs characterization

Not every test in a suite is asserting a product requirement, and a suite that
does not say which is which will be misread the first time it goes red.

| Class | What it asserts | A failure means | The right response |
|---|---|---|---|
| **Correctness test** | A requirement the shipped system must satisfy | The product is broken | Fix the product |
| **Compatibility characterization** | An observed property of an external system that a decision was derived from | The environment changed | Re-measure, then reconsider the ADR — *not* the product |

`tests/test_renderer_contract.py` carries both, and names them apart for this
reason:

```
TestRendererCorrectness                     4 tests
    every required glyph resolves through the approved fallback chain
    → red means the product is broken

TestRendererCompatibilityCharacterization   1 test
    on the supported wkhtmltopdf build, @font-face overrides fontconfig and fails
    → red means somebody upgraded the renderer and ADR-A4 is now in question
```

The second one is *designed* to fail the day a better wkhtmltopdf ships. That
failure is the signal working, and the class name is what tells the maintainer
which conversation to have instead of patching the product to make CI green.

**A related correction worth keeping**, because the first draft of the
correctness suite got it backwards:

```
WRONG    every PDF MUST embed Phetsarath and Noto Sans Lao
CORRECT  every required glyph MUST resolve through the approved fallback chain
```

An ordinary Lao invoice never needs Noto Sans Lao; its absence from that PDF is
correct, not a defect. Asserting an inventory of embedded fonts would have
failed on correct output and passed on a document whose fallback chain was
silently broken for the glyphs that need the second link. State the requirement
as the chain, and test the chain where it is observable — for us, on the 18
Pali/Sanskrit codepoints Noto covers and this build of Phetsarath does not.

---

## Severity vocabulary

Not every defect that shows up as "text looks slightly off" is cosmetic. This
repository distinguishes:

| Class | Meaning | Example |
|---|---|---|
| Typography / cosmetic | Looks wrong, reads correctly | Wrong font weight on a heading |
| **Document integrity / regulatory presentation risk** | **Output is plausible and wrong on a document that carries legal or tax weight** | Lao combining marks reordered by a fallback font on a tax invoice |
| Correctness | A computed value is wrong | Withholding tax at the wrong rate |

The middle class is the dangerous one, because the system's own success signals
report normal. It is also the class this repository produces most easily, since
it emits statutory documents in a script most of its maintainers cannot read.
