# Lane W2 report: KoverIQ package in the OpenMontage fork

Video Studio Phase 2, 2026-10-23. Branch `koveriq` of
https://github.com/root3you/OpenMontage (fork of `calesthio/OpenMontage`,
based on `c806645`). The final commit is the head of `origin/koveriq`
(`git log origin/koveriq`); the commits are listed at the end.

## What was delivered

| # | Deliverable | Where |
|---|---|---|
| 1 | Product-promo pipeline, `idea → script → scene_plan → assets → edit → compose`, no human gates, 3 revisions per stage, no research/proposal stage | `pipeline_defs/koveriq-product-promo.yaml`; `koveriq/checkpoints.py`; test `koveriq/tests/test_pipeline_def.py` |
| 2 | Director skill citing the upstream skills by path | `skills/koveriq/product-promo.md`, `skills/koveriq/README.md` |
| 3 | `tts_selector` fix (upstream-PR-ready, isolated in one commit) | `tools/provider_routing.py`, `tools/audio/piper_tts.py`, `tests/tools/test_tts_selector_piper_route.py` (commit `10d4b82`) |
| 4 | `koveriq` package: voices, slot schemas, grammar, templates, compose builder, tests | `koveriq/` |
| 5 | Deterministic golden + `make golden`, run on this machine | `koveriq/golden/`, `koveriq/koveriq.mk`, `docs/koveriq-golden.md` |
| 6 | Licence findings | `docs/koveriq-licences.md` |

Diff outside the KoverIQ areas: the TTS fix (2 files + its test) and a
3-line `include koveriq/koveriq.mk` in the root `Makefile`. No upstream file
was renamed or restructured.

## Voices and licences

- **Allowed:** `en_GB-cori-high` (default) and `en_GB-cori-medium`. Data is
  public-domain LibriVox recordings; both were trained from scratch. The files
  are pinned to piper-voices revision `5041a7a4…` with sha256 hashes I
  downloaded and verified.
- **Rejected (9):** alan-low/medium, alba, aru, jenny_dioco, vctk,
  northern_english_male, southern_english_female and semaine. Every one is
  fine-tuned from `en_US-lessac` (Blizzard 2013, research-only licence) or
  `en_US-ryan` (CC BY-NC-SA). Several also have NC, SA or all-rights-reserved
  data.
- **Consequence:** only one speaker (Cori, female) is commercially clean.
  There is no clean British male voice.
- **Unclear:**
  - Whether the lessac lineage really taints voices is legally untested; the
    maintainer says so himself.
  - Cori's status rests on the author's own statements.
  - The legal sign-off on the default voices is still a Phase 2 exit
    criterion (spec §10.2).
- **HyperFrames 0.8.185:** Apache-2.0, confirmed from npm and from the repo
  LICENSE ("Copyright 2026 HeyGen, Inc.").
  - Hosted commercial use is fine, so no FFmpeg fallback is needed.
  - The npm tarball ships no LICENSE file; add the text to the image.
  - **Telemetry is on by default.** `koveriq.hyperframes` and `make golden`
    turn it off, along with update checks and auto-installs. The worker must
    set the same variables.
- **GSAP 3.14.2:** GreenSock "Standard no-charge" licence. Commercial use is
  allowed, but there is no express redistribution right, and use in no-code
  visual animation builders is prohibited.
  - It is therefore **not committed**. `koveriq/vendor.py` fetches the npm
    tarball, checks its integrity and the file's sha256, and every build
    verifies the copy.
  - gsap.com was offline, so the licence text comes from mirrors. Re-check it.
- **Fonts:** Montserrat, Playfair Display and Archivo Black, all SIL OFL 1.1.
  HyperFrames embeds them, so nothing is downloaded at render time.

## Tests

- `koveriq/tests`: **252 passed**, plus 12 opt-in tests (the `hyperframes lint`
  sweep) that also pass when run with `KOVERIQ_HF_LINT=1` (12/12).
  - They run with no browser and no network. If GSAP was never fetched, a
    clearly fake stand-in is used.
  - **Coverage of the `koveriq` package is 99%** (1488 statements, 12 missed,
    tests excluded; pytest-cov).
- Full fork suite (`tests/` + `koveriq/tests`): **2313 passed**, 21 skipped,
  3 xfailed and **1 failed**.
  - The failure is `tests/tools/test_bmts_lite.py`, which needs a `python`
    executable on PATH. It also fails on an untouched checkout and is not
    related to this lane.
  - **Coverage of the whole fork is 74%**, mostly upstream OpenMontage code
    that this lane does not own. That is below the 95% target.
- `apply_params` was written alongside the builder. Its tests were
  mutation-checked: 4 mutants of the validators, each killed.

## Golden (`make golden`)

| Run | `hyperframes lint` | `snapshot` ×3 | `render` | **Total wall time** |
|---|---|---|---|---|
| 1 | 0 errors, 0 warnings | 6.9 s | 50.6 s | **59.8 s** |
| 2 | 0 errors, 0 warnings | 13.0 s | 56.9 s | **73.4 s** |
| 3 | 0 errors, 0 warnings | 6.6 s | 40.6 s | **50.3 s** |
| 4 (final code) | 0 errors, 0 warnings | 19.9 s | 41.3 s | **63.0 s** |

Every run produced an MP4 of 38.500 s at 1920×1080, 30 fps, H.264 + AAC.

- Both ffprobe assertions pass: duration within ±0.1 s, resolution
  1920×1080.
- Render speed is 1.05–1.5× real time on an M3 Max CPU.
- Loudness before packaging is −13.1 LUFS. The worker's packaging step has
  to normalise it to −16.
- `hyperframes check` also passes (`ok: true`) with 0 runtime, motion,
  contrast or craft findings.
- All 6 style × format builds containing all ten kinds lint with 0 errors and
  0 warnings, with no `nested_structure_needs_subcomposition` (one
  sub-composition per scene).

## Independent review

A separate reviewer read the builder, the schemas and all the templates.

- It found **no injection hole and no write outside the output folder.**
- It found nine robustness or timing issues, all reproduced as failing tests
  in `koveriq/tests/test_review_findings.py` and then fixed:
  1. A `NaN` `font_scale` or crop focus passed the params schema and crashed
     the rebuild after the old scene files had been deleted. Non-finite
     numbers are now refused, and a rebuild renders everything in memory
     before it replaces any file.
  2. `shorten_text` compared only letters and digits, so `20%` could become
     `£20`, and text in non-Latin scripts slipped through. It now compares
     whole visible words exactly; only the last kept word may drop its
     trailing punctuation.
  3. Wrong-typed slots or scene ids raised `TypeError` or `AttributeError`
     instead of `CompositionError`. They now raise `CompositionError`.
  4. A trailing newline passed the anchored patterns, because Python's `$`
     matches before a final `\n`. The checks now use `fullmatch`, and the
     schemas forbid the characters anywhere.
  5. A sideways pan with an off-centre focus showed a strip of background.
     Pans now scale around the centre.
  6. A non-string script title, and `scenes` that is not a list, crashed the
     build.
  7. A missing GSAP was reported as an input error. It now raises
     `GsapUnavailable`, so a runner does not retry the agent for an ops
     problem.
  8. In short scenes, entrances could still be fading in when the
     out-transition began. On square photo reveals, the cover painted over the
     text card. Words outside their scene still moved the beats. All three are
     fixed.
  9. Scene or asset ids that differ only by case collided on macOS and
     Windows file systems. They are now refused.
- A second review pass found six more, all fixed with regression tests:
  - `shorten_text` could still change a claim by dropping a middle word
    ("Free survey, fitting extra" → "Free fitting"). It now only cuts words
    off the end.
  - A decompression-bomb image escaped as a Pillow error; it is now an
    unreadable image.
  - A scene id could equal another scene's element id (`hero` and
    `hero-card`); scene ids may no longer contain `-`.
  - A list stored in `metadata.koveriq.scenes` crashed the build.
  - The corner mark doubled up on end cards; it is now hidden during every
    end card.
  - Extra non-JSON keys crashed `build.json`; only the keys the renderer
    uses are saved.
- Separately, I tightened `shorten_text` so that it cannot change a claim:
  see the `apply_params` rules below.

## Integration contract for W1

```python
from koveriq.compose import build_composition, apply_params, CompositionResult, CompositionError

@dataclass
class CompositionResult:
    index_html: pathlib.Path
    duration_ms: int
    hook_time_ms: int
    lint_warnings: list[str]

def build_composition(scene_plan: dict, script: dict, timings: dict, assets: dict[str, pathlib.Path],
                      style: str, fmt: str, brand: dict, out_dir: pathlib.Path,
                      *, captions: bool = False) -> CompositionResult: ...  # captions: lane W3
def apply_params(comp_dir: pathlib.Path, params: dict) -> None: ...
```

**Scene shape.** An OpenMontage `scene_plan` scene plus `kind`, `slots` and an
optional `role`:

```json
{
  "id": "sc2", "type": "broll", "description": "Product hero",
  "start_seconds": 5.5, "end_seconds": 13.05, "script_section_id": "s2",
  "role": "product",
  "kind": "photo_pan",
  "slots": {"assetId": "a-1", "overline": "Made to measure", "headline": "Made for your windows",
            "subline": "Bay windows, arches and awkward shapes", "focus": {"x": 0.5, "y": 0.4}}
}
```

- `id` must match `^[A-Za-z][A-Za-z0-9_]{0,31}$` and must not be one of
  `main`, `root`, `brand` or `narration`. There is no `-`, because element
  ids are `<sceneId>-<name>`. Ids that differ only by case are refused.
- Use `koveriq.scenes.KIND_TO_TYPE[kind]` for `type`.
- `kind` and `slots` must validate against `koveriq/scene_kinds.schema.json`.
  `koveriq.scenes.slot_errors` and `scene_plan_errors` return the errors as a
  list, for `write_artifact`.
- The scene order is checked by `koveriq.grammar.grammar_errors(plan,
  "product_promo", lengthSeconds, total_seconds=…)`. The word count is checked
  by `word_count_errors`.
- **Checkpoints:** OpenMontage's `scene_plan` schema forbids extra keys on a
  scene. Write `koveriq.scenes.to_checkpoint_scene_plan(plan)`, which moves
  kind, slots and role into `metadata.koveriq.scenes`. `build_composition`
  accepts both shapes.
- `koveriq.checkpoints.write_brief_checkpoint` and `write_stage_checkpoint`
  write checkpoints with `human_approved`, approver `koveriq:brief:{userId}`
  and approval policy `brief-preauth`.

**Timings** use the final video timeline:
- Values are integer ms. The first scene starts at 0.
- Each scene starts where the previous one ends, and lasts at least 1.5 s.
- Words outside their scene are ignored for beats and produce a warning.
- `duration_ms` is the sum of the spans; `hook_time_ms` is the first scene's
  midpoint.

**Assets and brand:**
- `assets` maps assetId to a JPEG, PNG or WebP. Only referenced photos are
  copied, to `assets/img/<assetId>.<ext>`.
- The optional key `"@narration"` takes a full-length wav, mp3, m4a or aac
  aligned to t=0, which HyperFrames then mixes in. Without it the MP4 is
  silent; mux the narration when packaging.
- `brand`:
  - `companyName`: at most 60 characters.
  - `website`: optional (lane W3: missing, None or "" means no website pill;
    the wordmark then closes the end card). When present, at most 80
    characters, no spaces; the scheme is stripped for display. It is shown
    only on the end card.
  - `logoPath`: PNG, JPEG, WebP or SVG.
  - `palette`: a partial override of `bg`, `surface`, `ink`, `muted`, `accent`
    and `accentInk`, each `#RRGGBB`.

**Output in `out_dir`:**
- `index.html`
- `compositions/<sceneId>.html`, plus `brand.html` for the corner mark
- `assets/{img,brand,audio,vendor}/`
- `.koveriq/build.json`, which `apply_params` rebuilds from

Rebuilding into the same directory replaces the generated files.

**Lane W3 additions.** `cta_endcard.cta` takes up to 120 characters (the
contract's `brief.cta`) and is never cut: two lines first, then three or four,
shrinking down to 45% of the base size, lines balanced. `captions=True` adds
`compositions/captions.html` on a `data-track-kind="captions"` track (2-3 word
groups from the timings' words, not on the end card) and lays the captioned
scenes out above the caption band; `captions` is a reserved scene id.

**`lint_warnings`** are the builder's own static checks, not HyperFrames lint:
- `text_fit:<sid>.<slot>`
- `text_floor:brand.companyName`
- `photo_upscaled:<sid>.<slot>`
- `palette_contrast:<fg>/<bg>`
- `word_outside_scene:<sid>.words[i]`
- `captions_empty:` (captions on, but no words in a captioned scene) and
  `text_fit:captions.g<N>` (lane W3)

Before rendering, run `koveriq.hyperframes.lint(comp_dir)`, which returns
errors and warnings. Then use `snapshot(...)` and `render(...)`. All three run
the pinned CLI in offline mode.

**`apply_params(comp_dir, params)`** takes params validated by
`koveriq/params.schema.json`:

```json
{"scenes": {"sc2": {"crop_focus": {"x": 0.3, "y": 0.6},
                    "shorten_text": {"headline": "Made for windows"},
                    "font_scale": 0.9}}}
```

- `shorten_text` must be the current line with whole words cut off its end.
  Only the last kept word may lose its trailing punctuation.
  - It must keep every negation ("no", "not", "without") and qualifier
    ("up", "from", "only").
  - It must keep all of the slot's figures or none of them.
  - `cta`, `offer`, `terms`, `badge` and `town` are never shortened.
- `crop_focus` only works on scenes that show a photo.
- A new revision replaces the previous one, because it is always applied to
  the original slots. Calling it twice is therefore idempotent, and the worker
  must enforce "once".
- Invalid params raise `CompositionError`, whose `.errors` you can return to
  the agent. Nothing is written in that case.

**Errors:**
- Invalid inputs raise `CompositionError(ValueError)` with `.errors`, a list of
  every problem found.
- A missing or tampered GSAP raises `koveriq.vendor.GsapUnavailable`, which is
  an environment error and not one to retry the agent on.
- Neither error writes anything to the output folder.

**Worker image:**
- Import `koveriq` from a source checkout of the fork (e.g. a submodule at a
  pinned commit) with the repo root on `PYTHONPATH`. Upstream's `setup.py`
  has no `package_data`: a wheel built from the fork carries the `.py` files
  but none of the templates, JSON schemas or YAML (upstream's `schemas/` are
  missing too). `koveriq` imports upstream `lib.checkpoint` and `schemas`.
- `pip install -r requirements.txt -r koveriq/requirements.txt` (Jinja2,
  MarkupSafe).
- Fetch GSAP at build time with `python -m koveriq.vendor fetch <path>` and set
  `KOVERIQ_GSAP_JS=<path>`.
- Node 22 or later, with `hyperframes@0.8.185` and its Chrome for Testing
  pre-cached.
- Set `HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1 HYPERFRAMES_NO_UPDATE_CHECK=1
  HYPERFRAMES_NO_AUTO_INSTALL=1 HYPERFRAMES_SKIP_SKILLS=1`.
- ffmpeg and ffprobe.
- Piper voices from `koveriq/voices.yaml`, checked against their sha256.
  `koveriq.voices.get_voice(id)` refuses any voice not on the list.

**TTS:** after the fix, `tts_selector` with `{"model": "en_GB-cori-high"}` (or
`{"voice": …}`) keeps Piper. A model that is not a Piper voice name still does
not route to Piper.

## Not done, and why

- **No upstream pull request.** The operator decides; the fix is
  self-contained in `10d4b82`.
- **No SSIM frame comparison or loudness assertion.** Spec §13.5 puts these in
  the worker's golden CI and they were not in this lane's brief. The golden's
  three snapshots can serve as references.
- **Other video types, and the Showroom and Minimal styles,** are Phase 3. The
  ten kinds already render in both styles and all formats.

## Risks

1. **Only one commercially clean voice** (Cori, female), and its legal
   sign-off is still open.
2. **GSAP licence.**
   - The licence text was only readable from mirrors.
   - A future no-code visual animation editor for tenants would need
     Webflow's consent.
3. **Text fitting** is measured from real glyph advances but ignores kerning;
   a 5% margin covers that.
   - The golden and the sweeps show no overflow.
   - Unusual text can still raise `text_fit` warnings. Snapshot review and
     `apply_params` are the remedy.
4. **Beat sync** matches the first word of each item label in the transcript.
   Numbers spoken differently ("89mm" vs "eighty-nine millimetre") fall back
   to even spacing.
5. **HyperFrames is pinned at 0.8.185.** Re-run `make koveriq-lint` and
   `make golden` on every bump, because lint rules change.
6. **Render speed on Cloud Run is unknown.** On the M3 Max it is 1.3–1.5× real
   time.
7. **The golden photos are CC BY-SA** and show a real company's work. They are
   attributed and labelled demo-only, and must never reach production.

## Commits on `origin/koveriq`

- `10d4b82` fix(tts): keep Piper on explicit routes when a Piper voice is requested
- `ed880b1` feat(koveriq): product-promo pipeline with a supplied-brief path
- `e46865b` feat(koveriq): scene-kind slot schemas and the product-promo grammar
- `eda2eee` feat(koveriq): deterministic HyperFrames compose builder and templates
- `0976076` feat(koveriq): voice allowlist, licence findings and the deterministic golden
- `9ecb24b` fix(koveriq): a shortened line may not change the claim
- `b999396` fix(koveriq): wrong-typed inputs raise CompositionError, not TypeError
- `a6b8783` fix(koveriq): address the independent review of the compose builder
- `4cf4d4c` docs(koveriq): lane W2 report
- `a71e893` fix(koveriq): second review pass of the compose builder
- the commit that brings this list up to date is the head of `origin/koveriq`

The commit trailers name Claude Opus 5.5, the model that did the work. The
brief asked for "Claude Fable 5.1"; the session's attribution rules use the
actual model.
