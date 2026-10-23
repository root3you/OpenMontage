"""Checkpoint helpers for the KoverIQ "brief supplied" path (spec §8.2).

The KoverIQ runner writes the `idea` stage itself, deterministically, from the
KoverIQ request. Every checkpoint is written `human_approved=True` with the
approver `koveriq:brief:{userId}`: the user who submitted the brief approved
the whole run up front. The decision log records that as an
`approval_policy` decision (`brief-preauth`), which is how OpenMontage's
checkpoint protocol records a full-run pre-authorisation.

These helpers only wrap `lib.checkpoint.write_checkpoint`; the pipeline
manifest (`pipeline_defs/koveriq-product-promo.yaml`) stays the authority for
stage order and gates.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Optional

from lib.checkpoint import write_checkpoint

PRODUCT_PROMO_PIPELINE = "koveriq-product-promo"
APPROVAL_POLICY = "brief-preauth"


def approver(user_id: str) -> str:
    """The approver recorded on every checkpoint of a KoverIQ render."""
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id is required to record the brief approver")
    return f"koveriq:brief:{user_id}"


def brief_decision_log(project_id: str) -> dict[str, Any]:
    """Decisions the runner makes when it writes the brief.

    Both are fixed by the KoverIQ product, not chosen per render, and both are
    recorded with the alternatives that were rejected so a reviewer can see
    them.
    """
    return {
        "version": "1.0",
        "project_id": project_id,
        "decisions": [
            {
                "decision_id": "koveriq-brief-001",
                "stage": "idea",
                "category": "approval_policy",
                "subject": "Gate approvals",
                "options_considered": [
                    {
                        "option_id": APPROVAL_POLICY,
                        "label": "The submitted KoverIQ brief pre-authorises the whole run",
                        "score": 1.0,
                        "reason": "The user fixed product, facts, length, formats, voice and CTA in the brief "
                        "and reviews the finished video before any use; nothing is posted automatically.",
                    },
                    {
                        "option_id": "interactive",
                        "label": "Stop at every human gate",
                        "score": 0.0,
                        "reason": "The worker runs unattended.",
                        "rejected_because": "No human is attached to a render; users re-render instead.",
                    },
                ],
                "selected": APPROVAL_POLICY,
                "reason": "Spec §8.2: human gates inside a render are replaced by the submitted brief.",
                "user_visible": True,
                "user_approved": True,
            },
            {
                "decision_id": "koveriq-brief-002",
                "stage": "idea",
                "category": "render_runtime_selection",
                "subject": "Composition runtime",
                "options_considered": [
                    {
                        "option_id": "hyperframes",
                        "label": "HyperFrames (HTML/CSS/GSAP) with the KoverIQ templates",
                        "score": 1.0,
                        "reason": "Deterministic KoverIQ scene-kind templates exist only for HyperFrames; "
                        "Apache-2.0 runtime, renders on CPU.",
                    },
                    {
                        "option_id": "remotion",
                        "label": "Remotion (React scene stack)",
                        "score": 0.0,
                        "reason": "No KoverIQ templates.",
                        "rejected_because": "Needs a paid company licence above a small-team size (spec §10.2).",
                    },
                    {
                        "option_id": "ffmpeg",
                        "label": "FFmpeg only",
                        "score": 0.1,
                        "reason": "Slideshow only.",
                        "rejected_because": "Fallback only if the HyperFrames licence check fails (spec §10.2).",
                    },
                ],
                "selected": "hyperframes",
                "reason": "The KoverIQ pipelines are locked to HyperFrames; the agent cannot change runtime.",
                "user_visible": True,
                "user_approved": True,
            },
        ],
    }


def write_stage_checkpoint(
    pipeline_dir: Path,
    project_id: str,
    stage: str,
    artifacts: dict[str, Any],
    *,
    user_id: str,
    pipeline_type: str = PRODUCT_PROMO_PIPELINE,
    status: str = "completed",
    metadata: Optional[dict[str, Any]] = None,
) -> Path:
    """Write a stage checkpoint approved under the submitted brief."""
    meta = dict(metadata or {})
    meta["approval_policy"] = APPROVAL_POLICY
    meta["approved_by"] = approver(user_id)
    return write_checkpoint(
        pipeline_dir,
        project_id,
        stage,
        status,
        artifacts,
        pipeline_type=pipeline_type,
        human_approved=True,
        metadata=meta,
    )


def write_brief_checkpoint(
    pipeline_dir: Path,
    project_id: str,
    brief: dict[str, Any],
    *,
    user_id: str,
    pipeline_type: str = PRODUCT_PROMO_PIPELINE,
) -> Path:
    """Write the `idea` checkpoint from a brief the runner built from the request.

    The brief must already be a schema-valid OpenMontage `brief` artifact; the
    checkpoint writer validates it. Its `metadata.approval_policy` is set to
    `brief-preauth` (a different value is refused rather than overwritten).
    """
    brief = copy.deepcopy(brief)
    metadata = brief.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("brief.metadata must be an object")
    existing = metadata.get("approval_policy")
    if existing not in (None, APPROVAL_POLICY):
        raise ValueError(
            f"brief.metadata.approval_policy is {existing!r}; KoverIQ briefs are always {APPROVAL_POLICY!r}"
        )
    metadata["approval_policy"] = APPROVAL_POLICY
    artifacts = {"brief": brief, "decision_log": brief_decision_log(project_id)}
    return write_stage_checkpoint(
        pipeline_dir,
        project_id,
        "idea",
        artifacts,
        user_id=user_id,
        pipeline_type=pipeline_type,
    )
