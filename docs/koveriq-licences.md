# KoverIQ fork: licence findings

Checked 2026-10-23 for Video Studio Phase 2 (spec §10). Sources were fetched
directly; the voice files were downloaded and hashed. This is an engineering
record, not legal advice: the items under "Unclear" need the operator's (or
counsel's) decision before production.

## Summary

| Component | Licence | Verdict | How the fork complies |
|---|---|---|---|
| Piper voice `en_GB-cori-high` | Public domain (LibriVox data, trained from scratch) | **Allowed** (default voice) | Listed in `koveriq/voices.yaml` with pinned URLs and sha256 |
| Piper voice `en_GB-cori-medium` | Same | **Allowed** | Same |
| The other 9 en_GB Piper voices | NC / SA / all-rights-reserved data, or a research-only base model | **Rejected** | Listed under `rejected:` with the reason; `get_voice()` refuses them |
| Piper engine (`piper-tts` ≥ 1.3, piper1-gpl) | GPL-3.0-or-later | Allowed | Separate process in the worker; source published with the worker |
| HyperFrames CLI 0.8.185 | Apache-2.0 | **Allowed** for hosted commercial use | Pinned version; telemetry and update checks off |
| GSAP 3.14.2 | GreenSock "Standard no charge" licence (Webflow) | Use allowed; **redistribution unclear** | **Not committed**; fetched at build time with pinned integrity |
| Montserrat, Playfair Display, Archivo Black | SIL OFL 1.1 | Allowed | Embedded by HyperFrames; not shipped by the fork |
| OpenMontage | AGPL-3.0 | — | Public fork; the `koveriq/` package is part of it |
| Golden demo photos | CC BY-SA 4.0 | Golden only, **never production** | Attributed in `koveriq/golden/README.md` |

## Piper voices

Every en_GB voice in `rhasspy/piper-voices` (revision
`5041a7a49ae5b3a0f30e6837769eb03fdbb231bd`, 11 voice/quality pairs) was
checked: its `MODEL_CARD`, the dataset licence it points to, and the
checkpoint it was fine-tuned from.

**The lineage decides it.** Seven of the nine rejected voices are
"Finetuned from U.S. English lessac voice", whose model card points to the
Blizzard 2013 Lessac licence: "This data is released under a license for
non-commercial use only" (research purposes only, explicitly excluding
commercial voice-synthesis products). Two are fine-tuned from `en_US-ryan-low`
(RyanSpeech, CC BY-NC-SA 4.0). The Piper maintainer says the question "has not
been tested yet legally" and is retraining voices on a CC BY base
(LibriTTS-R) "so that they can at least be used for commercial purposes"; no
en_GB voice has been retrained yet
(https://huggingface.co/rhasspy/piper-voices/discussions/94).

### Allowed

| voiceId | Dataset | Licence evidence | Training |
|---|---|---|---|
| `en_GB-cori-high` | LibriVox recordings read by "Cori", about 24 h, assembled by Bryce Beattie | Model card: "License: public domain"; author page (https://brycebeattie.com/files/tts/): "License: public domain", "Feel free to use these for any legal and ethical purpose"; LibriVox: "all our recordings are public domain … anyone can use all our recordings however they wish (even to sell them)" | "Trained from scratch … for 500 epochs" |
| `en_GB-cori-medium` | Same | Same | "Trained from scratch … for 640 epochs" |

Both `.onnx` files are byte-identical to the author's own release (md5
match). sha256 values in `voices.yaml` were computed from downloaded files.
Attribution is not required; `voices.yaml` carries an optional credit line.

### Rejected

| voiceId | Why |
|---|---|
| `en_GB-alan-low` | Data (Mycroft mimic3 `apope_low`): "All Rights Reserved"; base `en_US-ryan-low` (CC BY-NC-SA) |
| `en_GB-alan-medium` | "All Rights Reserved" data; base lessac (research-only) |
| `en_GB-alba-medium` | Data CC BY 4.0, but base lessac; the data licence also prohibits "use derogatory to the voice talent" |
| `en_GB-aru-medium` | Data CC BY (3.0 vs 4.0 listed inconsistently), base lessac |
| `en_GB-jenny_dioco-medium` | Data allows commercial use (attribution "Jenny (Dioco)"), base lessac; speaker is Irish |
| `en_GB-northern_english_male-medium` | Data CC BY-SA 4.0 (share-alike, refused by spec §10.3), base lessac |
| `en_GB-semaine-medium` | Data CC BY-NC-SA 4.0 (non-commercial), base lessac |
| `en_GB-southern_english_female-low` | Data CC BY-SA 4.0, base ryan (CC BY-NC-SA) |
| `en_GB-vctk-medium` | Data CC BY 4.0, base lessac |

Consequence: **only one speaker (Cori, female) is commercially clean.** There
is no clean British male voice today. Options for the operator: ship with Cori
only; wait for Piper's CC BY-based retrains; or fine-tune a voice ourselves
from the CC BY LibriTTS-R base on CC BY data (for example a VCTK speaker),
which is a separate piece of work.

The Piper docs say Piper "is intended for personal use and text to speech
research only; we do not impose any additional restrictions on voice models".
That is a statement of intent, not a licence term.

## Piper engine

`OHF-Voice/piper1-gpl` is GPL-3.0 (`COPYING`); the `piper-tts` PyPI package is
GPL-3.0-or-later from 1.3.0 (1.2.0 and earlier were MIT, from the archived
`rhasspy/piper`). It runs as a separate process in the worker, which is
published under AGPL-3.0 (AGPL §13 allows combination with GPL-3.0 works).
Generated audio is program output and is not covered by the GPL
(https://www.gnu.org/licenses/gpl-faq.html#WhatCaseIsOutputGPL).

## HyperFrames

- `npm view hyperframes@0.8.185 license` → `Apache-2.0`; the repository
  LICENSE (https://github.com/heygen-com/hyperframes) is the Apache License 2.0,
  "Copyright 2026 HeyGen, Inc." No NOTICE file at the root; no separately
  licensed CLI, studio or registry directories. The README: "Open source:
  Apache 2.0 license, with no per-render fees or commercial-use thresholds."
- **The npm tarball ships no LICENSE file.** An image that bakes the CLI in
  should add the Apache-2.0 text.
- **Telemetry is on by default** (anonymous usage to PostHog).
  `koveriq.hyperframes` and `make golden` set `HYPERFRAMES_NO_TELEMETRY=1` and
  `DO_NOT_TRACK=1`, plus `HYPERFRAMES_NO_UPDATE_CHECK=1`,
  `HYPERFRAMES_NO_AUTO_INSTALL=1` and `HYPERFRAMES_SKIP_SKILLS=1`, so a render
  makes no network call once the CLI and its browser are cached. The worker
  must set the same variables.
- It renders with Chrome for Testing (`chrome-headless-shell` 152.0.7977.30
  on this machine), downloaded on first use into `~/.cache/hyperframes`
  (Chromium licences, BSD-style). Bake it into the image.
- Fonts used by the templates are embedded in the CLI (`@fontsource` builds),
  so no font is downloaded at render time.
- The CLI's own dependencies (puppeteer-core, esbuild, hono, …) were not
  audited one by one. The registry blocks (some marked "origin to be
  confirmed") are not used by the KoverIQ templates.

The spec's assumption (§10.2) holds: HyperFrames' licence allows hosted
commercial use, so the FFmpeg-only fallback is not needed.

## GSAP

HyperFrames compositions animate with GSAP. `gsap@3.14.2` declares
"Standard 'no charge' license: https://gsap.com/standard-license", and its
`dist/gsap.min.js` header reads "Copyright 2025, GreenSock. All rights
reserved. Subject to the terms at https://gsap.com/standard-license."

gsap.com was offline on 2026-10-23; the text below comes from two mirrors
(ScanCode LicenseDB, effective 30 April 2025; TOSTracker, modified 30 May
2025). Re-check it on gsap.com.

- Grant: "a non-exclusive, worldwide license to use, reproduce, display, and
  implement GSAP Products solely for Permitted Uses" — use "on any website,
  web application, or digital interface".
- FAQ: "Commercial usage is covered under the standard license."
- Prohibited: use "in tools that allow users to build visual animations
  without code" that compete with Webflow's visual animation builder.
- No express right to redistribute or sublicense.

Decisions:

1. **GSAP is not committed to this AGPL repository.** AGPL §10 forbids further
   restrictions on the covered work, and the GSAP licence has use restrictions
   and no redistribution grant. `koveriq/vendor.py` fetches the pinned npm
   tarball at build time (`make koveriq-vendor`, or the image build), checks
   the npm integrity (`sha512-P8/mMx…BLA==`) and the file's sha256
   (`c174bfce…8280`), and every build verifies the copy it ships into the
   composition. The GreenSock header stays intact.
2. Rendering KoverIQ templates in a hosted service reads as a Permitted Use.
   **A future visual (no-code) animation or timeline editor for tenants would
   need Webflow's written consent**; spec §1.2 rules a timeline editor out for
   v1.

## Fonts

| Family | Licence | Weights the templates use |
|---|---|---|
| Montserrat | SIL OFL 1.1 ("Copyright 2024 The Montserrat.Git Project Authors") | 400, 700, 900 |
| Playfair Display | SIL OFL 1.1 (Reserved Font Name "Playfair Display") | 900 |
| Archivo Black | SIL OFL 1.1 | 400 |

Sources: `@fontsource/<family>` npm metadata (`OFL-1.1`) and google/fonts
`OFL.txt`. The fork ships no font files (HyperFrames embeds them), and the OFL
does not extend to videos made with the fonts. If the worker image
redistributes font files, it must include the OFL text and copyright notices
(the hyperframes tarball does not).

`koveriq/font_metrics.json` holds glyph advance widths measured from those
fonts (numbers only, no font data).

## Golden demo inputs

`koveriq/golden/assets/` holds three CC BY-SA 4.0 Wikimedia Commons photos
(two credited to a real shutter company) from the spike, cropped. They are
attributed in `koveriq/golden/README.md` and are **only** for the golden; spec
§10.3 refuses CC BY-SA assets in production. The golden narration was made
with `en_GB-cori-high`. The golden brand is "Demo Shutters Co." at
`demo-shutters.example` (a reserved, never-real domain).

## Unclear: needs a decision

1. **Voice lineage.** Rejecting every lessac- or ryan-derived voice is the
   cautious reading; the question is legally untested. Only Cori is clean.
2. **Cori rests on the author's statements** ("trained from scratch", "public
   domain"). The dataset is not published and the LibriVox reader is not
   named, so the reader's personality rights are not addressed (low risk for
   ads). Spec §10.2 makes "a legal check of the two default voices" a Phase 2
   exit criterion: that sign-off is still needed.
3. **GSAP redistribution** (why it is fetched, not committed) and the
   "Prohibited Uses" wording, which is vague. The licence page could only be
   read from mirrors.
4. **HyperFrames dependencies and Chrome for Testing** were not audited
   package by package.
