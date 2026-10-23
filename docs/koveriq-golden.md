# KoverIQ golden render: results

The deterministic golden (`koveriq/golden/`, `make golden`) builds the
`clean` 16:9 product promo from fixed inputs, lints it, snapshots it at three
times, renders it with HyperFrames and checks the MP4 with ffprobe. Inputs and
licences: `koveriq/golden/README.md`.

## Runs on this machine (2026-10-23)

Apple M3 Max, 128 GB, macOS 26.2, CPU render (no GPU flags), Node 24.20,
ffmpeg 8.1.2, Python 3.11.15 (uv), `hyperframes@0.8.185` and its Chrome for
Testing (`chrome-headless-shell` 152.0.7977.30) already cached, render quality
`standard`, 30 fps.

| Run | Code | build | `lint` | `snapshot` ×3 | `render` | **Total wall** (`time make golden`) |
|---|---|---|---|---|---|---|
| 1 | before the 28 px text-floor fix | 0.07 s | 1.05 s, 0 errors, 0 warnings | 6.90 s | 50.55 s | **59.8 s** |
| 2 | after the text-floor fix | 0.21 s | 1.31 s, 0 errors, 0 warnings | 12.95 s | 56.85 s | **73.4 s** |
| 3 | after the first review fixes | 0.06 s | 0.84 s, 0 errors, 0 warnings | 6.63 s | 40.59 s | **50.3 s** |
| 4 | final (after the second review pass) | 0.08 s | 0.75 s, 0 errors, 0 warnings | 19.86 s | 41.32 s | **63.0 s** |
| 5 | lane W3 (CTA fit ladder, optional website, captions code; the golden keeps captions off) | 0.11 s | 1.16 s, 0 errors, 0 warnings | 6.87 s | 36.62 s | **45.5 s** |

All runs used the same inputs. The spread, mostly in the snapshot step, is
machine load.

Output of the final W2 run (every run, W3's run 5 included, measured the same duration, size and loudness):

| Check | Expected | Measured | Result |
|---|---|---|---|
| Duration (ffprobe) | 38.5 s ± 0.1 s | 38.500 s | pass |
| Resolution | 1920×1080 | 1920×1080 | pass |
| Frame rate | 30 fps | 30 fps | pass |
| Streams | — | H.264 video, AAC audio | — |
| File size | — | 10.4 MB | — |
| Integrated loudness | −16 ±1 LUFS after the worker's packaging (spec §13.5) | −13.1 LUFS before packaging | not normalised here |

Render speed: 38.5 s of video in about 41–57 s, i.e. **1.05–1.5× real time**
(the spike measured 1.8× warm at `quality=high`).

`hyperframes check --samples 15` on the same composition (browser audits, not
required by the golden): `ok: true`; 0 runtime, motion, contrast or craft
findings; 3 `container_overflow` infos for the photos' Ken Burns push inside
their clipping frames (intended).

## Notes for the worker

- Loudness normalisation to −16 LUFS is the render stage's FFmpeg packaging
  step (spec §5.4); the composition mixes the narration at its source level.
- Frame comparison (SSIM ≥ 0.98, spec §13.5) is not part of this golden; the
  three snapshots in `out/snapshots/` are the natural references for it.
- Run with `KOVERIQ_HYPERFRAMES_VERSION` unset to stay on the pinned 0.8.185;
  `koveriq.hyperframes` switches off telemetry, update checks and auto-install.

## Lane W3 evidence (captions and the end card)

The golden keeps captions off. The rendered evidence for burned-in captions
and for the end card's CTA (40/80/120 characters, with and without a website)
is the opt-in suite `KOVERIQ_HF_SNAPSHOT=1 pytest koveriq/tests/test_snapshots.py`
(24 cases, about 5 minutes): every case is linted, audited with `hyperframes
check` (no held layout error; with captions on, `--caption-zone` fails any scene
text inside the caption band) and snapshotted, with one contact sheet per case
in `output/koveriq-snapshots/` (git-ignored; `make golden` wipes
`koveriq/golden/out/`, so the evidence lives outside it).
