# KoverIQ deterministic golden

A fixed product promo (6 scenes, 38.5 s) rendered through the real templates
and the real HyperFrames CLI:

    make golden          # or: python -m koveriq.golden [--quality draft|standard|high]

It builds the `clean` 16:9 composition, runs `hyperframes lint` (must report 0
errors), takes `hyperframes snapshot` frames at 2.75 s, 15.8 s and 36.5 s,
renders the MP4 with `hyperframes render`, and checks with ffprobe that the
MP4 lasts 38.5 s ± 0.1 s and is 1920×1080. Results go to `out/` (git-ignored):
`out/golden-report.json`, `out/snapshots/`, `out/golden-clean-16x9.mp4`.
Measured runs are recorded in `docs/koveriq-golden.md`.

Prerequisites: Node 22+ with the `hyperframes@0.8.185` CLI in the npx cache
(its Chrome downloads once into `~/.cache/hyperframes`), ffmpeg/ffprobe, and the
pinned GSAP (`make koveriq-vendor` fetches it once).

## Inputs

| File | What |
|---|---|
| `script.json` | OpenMontage script: the spike's six narration sections |
| `scene_plan.json` | Scene plan with KoverIQ `role`, `kind` and `slots` per scene: photo_reveal → photo_pan → swatches → text_card → steps → cta_endcard |
| `timings.json` | Scene spans from the spike's `edit_decisions.json` and the faster-whisper word timings of its narration, on the video timeline |
| `brand.json` | "Demo Shutters Co." at `demo-shutters.example` (a reserved domain that can never be real) |
| `expected.json` | Expected duration, hook time, resolution, fps, snapshot times |
| `assets/narration.m4a` | The spike's narration (Piper `en_GB-cori-high`, loudness-normalised per section), placed at the spike's section offsets in one mono track |
| `assets/a-*.jpg` | Three photos, see below |

`koveriq/tools/make_golden_inputs.py` regenerates all of these from the spike
project (`projects/plantation-shutters-promo`).

## Photos: CC BY-SA demo inputs, NOT for production

These photos are licensed CC BY-SA 4.0 and two of them name a real shutter
company. They exist only to exercise the templates. KoverIQ production renders
accept only tenant-owned or KoverIQ-original assets and refuse CC BY-SA (spec
§10.3). Do not reuse them anywhere else.

| File | Title | Author | Source | Licence | Changes |
|---|---|---|---|---|---|
| `a-bay.jpg` | White California shutters fitted to a bay window in Toronto | Gtashutters.com | https://commons.wikimedia.org/wiki/File:White_California_shutters_fitted_to_a_bay_window_in_Toronto.jpg | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | Resized from 4032×3024 to 2400×1800 |
| `a-arches.jpg` | 2 Louvers Plantation Shutters | Shuttersfla | https://commons.wikimedia.org/wiki/File:2_Louvers_Plantation_Shutters.jpg | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | Cropped (removes a helmet with a team logo) and resized to 2400×1730 |
| `a-living.jpg` | White California shutters fitted to living room windows in Toronto | Gtashutters.com | https://commons.wikimedia.org/wiki/File:White_California_shutters_fitted_to_living_room_windows_in_Toronto.jpg | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | Cropped to the left window and resized to 1400×1852 |

The modified photos are offered under the same licence (CC BY-SA 4.0).

## Install showcase golden

    make golden-install   # or: python -m koveriq.golden.install [--update-reference]

The install-showcase plan (before → reveal → details → town card → CTA, 30 s)
on three synthetic photos, built in 9:16 and 1:1 (clean), linted (0 errors),
snapshotted at 2.5, 8, 23.25 and 27.5 s and compared with SSIM ≥ 0.98 against
`install-showcase/reference/` (luma, half size), then rendered and checked
with ffprobe (30 s ± 0.1 s, 1080×1920 and 1080×1080). There is no narration,
so the frames depend on the templates alone. Results go to `out/install/`.

References are made with `--update-reference` and compare only on the platform
that made them (`reference/meta.json`); elsewhere the SSIM step is reported as
skipped. Remake them, and look at them, whenever a template change is meant to
change the picture.

The photos are KoverIQ-original artwork drawn by `install_photos.py` (licence
`koveriq_original`, no photograph, no person, no house number). Regenerate them
with `python -m koveriq.golden.install_photos`; a test fails if the committed
files differ from what the generator draws.
