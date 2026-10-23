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

| Step | Run 1 | Run 2 | Run 3 (final) |
|---|---|---|---|
| build (`build_composition`) | 0.07 s | 0.21 s | 0.06 s |
| `hyperframes lint` | 1.05 s, 0 errors, 0 warnings | 1.31 s, 0 errors, 0 warnings | 0.84 s, 0 errors, 0 warnings |
| `hyperframes snapshot` ×3 | 6.90 s | 12.95 s | 6.63 s |
| `hyperframes render` | 50.55 s | 56.85 s | 40.59 s |
| **Total wall time** (`time make golden`) | **59.8 s** | **73.4 s** | **50.3 s** |

Run 3 is the final code (after the review fixes, commit on `origin/koveriq`);
runs 1 and 2 were earlier template revisions with the same inputs. The spread
is mostly machine load.

Output of run 3 (runs 1 and 2 measured the same duration, size and loudness):

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
