# KoverIQ skills

Concise director skills for the KoverIQ video worker's headless agent. They
replace OpenMontage's interactive directors for the KoverIQ pipelines and cite
upstream skills by path instead of restating them, so the agent's context
stays small and its cached system prefix stays stable.

| Skill | Pipeline | Stages |
|---|---|---|
| `product-promo.md` | `pipeline_defs/koveriq-product-promo.yaml` | all six (`idea` is written by runner code) |

Campaign ad, install showcase and explainer skills arrive with their pipelines
(Phase 3).

## How the worker uses them

- The worker's `read_skill(name)` tool serves only allowlisted files: these
  skills plus the upstream sections each one cites.
- The rules here are enforced in code as well: `write_artifact` validates
  every artifact against the OpenMontage schemas, `koveriq/scene_kinds.schema.json`,
  `koveriq/scene_grammar.yaml` and the KoverIQ guardrails (spec §8.5).
- Rendering is deterministic: `koveriq.compose.build_composition` turns the
  scene plan, script and word timings into a HyperFrames project from
  `koveriq/templates/`; the agent never writes HTML.
