# Font provenance

These files are **not** GPL-3.0 like the rest of this repository. Both families are SIL
Open Font License 1.1, which permits bundling and redistribution inside other software
provided the licence travels with the font. `LICENSE-PHETSARATH.txt` and
`LICENSE-NOTO.txt` are those licences and must not be removed.

Neither copyright notice declares a Reserved Font Name, so instancing and renaming are
unrestricted.

This file exists so the 332 KB in this directory is **reproducible rather than merely
vendored**. Every hash below can be recomputed with `sha256sum`.

---

## Phetsarath — shipped unmodified

*Copyright (c) 2010-2012, Ministry of Posts and Telecommunications, Laos
(www.phetsarath.gov.la)* — the official Lao government font.

| | |
|---|---|
| Upstream | `https://raw.githubusercontent.com/google/fonts/main/ofl/phetsarath/` |
| Retrieved | 2026-09-16 |
| Licence | SIL OFL 1.1, no Reserved Font Name |
| Transformation | **none** — byte-identical to upstream |

| File | SHA-256 | Bytes |
|---|---|---|
| `Phetsarath-Regular.ttf` | `0d0328c2036319a06ae4e0093d1ea32b6d849069f624cf6dd67e1f6ebc4635a8` | 40,544 |
| `Phetsarath-Bold.ttf` | `3b8cced65a9b4a49da487c4abb6c36c9dafb2c11e3c75a16b7da32a28bc2ecab` | 156,840 |

Regenerate:

```bash
curl -sSL -O https://raw.githubusercontent.com/google/fonts/main/ofl/phetsarath/Phetsarath-Regular.ttf
curl -sSL -O https://raw.githubusercontent.com/google/fonts/main/ofl/phetsarath/Phetsarath-Bold.ttf
curl -sSL -o LICENSE-PHETSARATH.txt https://raw.githubusercontent.com/google/fonts/main/ofl/phetsarath/OFL.txt
```

---

## Noto Sans Lao — static instances built from the upstream variable font

*Copyright 2022 The Noto Project Authors (https://github.com/notofonts/lao)*

`google/fonts` ships Noto Sans Lao **only as a variable font**, and the supported bERP PDF
renderer cannot use one. The two statics here were instanced from it.

| | |
|---|---|
| Upstream | `https://raw.githubusercontent.com/google/fonts/main/ofl/notosanslao/NotoSansLao[wdth,wght].ttf` |
| Upstream SHA-256 | `9608b94603a82d09a8038946f9775242f99e3b3459b7f1e4d5b335b578cd7ab3` (176,620 bytes) |
| Retrieved | 2026-09-16 |
| Licence | SIL OFL 1.1, no Reserved Font Name |
| Transformation | `fontTools.varLib.instancer`, pinning `wdth=100` and `wght` to 400 / 700, then name records 1, 2, 4 and 6 set for the instance |
| Built with | `fonttools` (pip), Python 3.11 |

| File | SHA-256 | Bytes |
|---|---|---|
| `NotoSansLao-Regular.ttf` | `bdef30837298f2e66ba235f6a02820bdec4122ac48ce160795c58c4a0b5aff52` | 52,828 |
| `NotoSansLao-Bold.ttf` | `3ce3199167399b74e1cc3ec87187352c1c26332af743f1da6efd2c41e6b4eba9` | 52,972 |

⚠️ **The generated hashes are not guaranteed stable across fontTools versions.** Treat
them as a record of what was shipped, not as a reproducibility assertion about future
builds. If regeneration yields different bytes, compare the name records, the axis values
and the glyph coverage rather than the hash.

Regenerate:

```bash
curl -sSL -o 'NotoSansLao[wdth,wght].ttf' \
  'https://raw.githubusercontent.com/google/fonts/main/ofl/notosanslao/NotoSansLao%5Bwdth,wght%5D.ttf'
curl -sSL -o LICENSE-NOTO.txt \
  https://raw.githubusercontent.com/google/fonts/main/ofl/notosanslao/OFL.txt

python3 - <<'PY'
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

for weight, style in ((400, "Regular"), (700, "Bold")):
    f = TTFont("NotoSansLao[wdth,wght].ttf")
    instancer.instantiateVariableFont(f, {"wght": weight, "wdth": 100}, inplace=True)
    n = f["name"]
    n.setName("Noto Sans Lao", 1, 3, 1, 0x409)
    n.setName(style, 2, 3, 1, 0x409)
    n.setName(f"Noto Sans Lao {style}", 4, 3, 1, 0x409)
    n.setName(f"NotoSansLao-{style}", 6, 3, 1, 0x409)
    f.save(f"NotoSansLao-{style}.ttf")
PY
```

---

## Why both families, and in this order

| Family | Lao codepoints covered (U+0E80–U+0EFF) |
|---|---|
| Phetsarath | 65 |
| Noto Sans Lao | 83 |

Phetsarath leads every document fallback chain because it is the government font and is
what a Lao tax office expects to see. It is also the **narrower** of the two, so Noto Sans
Lao follows it everywhere as the wider net.

`tests/test_lao_fonts.py` fails if any file here is a variable font, or if a family ships
without its licence.

## Upgrade path

MTS Lao publishes a rebuilt **Phetsarath OT v4.103** at
<https://fonts.mts.la/f/phetsarath-ot> — twelve styles, corrected Lao word-wrapping in MS
Office, and Pali/Sanskrit letters this 2011-vintage build lacks. Also OFL 1.1. The
internal family name is the same, so it is a straight file replacement; update the hashes
and the retrieval date above when it happens. Worth doing before the app carries documents
containing Pali text.
