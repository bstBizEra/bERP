# Wordmark re-export requirement

**Status:** open — needs Illustrator, cannot be fixed by script
**Affects:** `Brandkit/Logo/SVG/bERP_Logo_hText.svg`, `bERP_Logo_vText.svg`
**Detected by:** `scripts/check_branding.py` check `D4`
**Raised:** 2026-09-19

## What is wrong

Both wordmark SVGs carry a live `<text>` element rather than outlined paths:

```xml
<text class="cls-4" transform="translate(345.96 360.78)">
  <tspan>PEOPLE - PLATFORMS - POSSIBILITIES</tspan>
</text>
```

with

```css
.cls-4 { font-family: Inter-Regular, Inter; font-size: 34.75px; }
```

The mark itself is vector. Only the tagline is live text.

## Why it matters

The tagline renders in whatever face the host resolves for `Inter`. Where Inter is
installed it looks correct. Where it is not — most servers, most PDF renderers, any
machine without Inter — the renderer silently substitutes another face and the
tagline sets at a different width, weight and rhythm.

This is the same failure shape as the Phetsarath/DejaVu incident recorded in
`docs/REVIEW-METHOD.md`: **it does not break, it renders wrong on output that still
looks finished.** Nobody gets an error. A tenant gets a quotation with a subtly
wrong logo.

It is worse for a logo than for body text, because a wordmark is an identity asset —
the letterforms *are* the trademark. A substituted face is not the bERP wordmark.

`bERP_Logo_Icon.svg` has no text and is unaffected. That is why the app ships the
icon and not the wordmark.

## What to do

In Illustrator, from `Brandkit/Logo/20260917_Logo.ai`:

1. Select the tagline text.
2. **Type → Create Outlines** (`Ctrl+Shift+O`).
3. Re-export both `bERP_Logo_hText.svg` and `bERP_Logo_vText.svg`.
4. On export, prefer **Styling: Presentation Attributes** over an internal `<style>`
   block — that also clears the `.cls-N` collision warning (`D5`).
5. Keep a live-text master. Outline on export, never in the working file.

## How to confirm the fix

```bash
python3 scripts/check_branding.py --assets /path/to/Brandkit/Logo
```

`D4` must report `PASS  … SVG fully outlined`. There is no partial credit: the check
counts `<text>` elements and any one of them fails it.

## Also open

`D2` — `logo.inverse` is missing. BERP-WL-001 §17 lists five required assets; the kit
provides the mark and the wordmark. A light/white treatment for dark backgrounds is a
design decision, not a colour substitution, so it is not something to generate.
