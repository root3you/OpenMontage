"""The KoverIQ product-promo pipeline: supplied brief, no human gates.

Spec §8.1/§8.2: the KoverIQ pipelines start at `idea` with a brief the runner
writes from the request, so the checkpoint writer's prerequisite check is met
honestly — no research brief and no invented sources.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from koveriq.checkpoints import (
    APPROVAL_POLICY,
    PRODUCT_PROMO_PIPELINE,
    approver,
    write_brief_checkpoint,
    write_stage_checkpoint,
)
from lib.checkpoint import (
    CheckpointValidationError,
    _enforce_stage_prerequisites,
    get_pipeline_stages,
    init_project,
)
from lib.pipeline_loader import get_stage_order, load_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGES = ["idea", "script", "scene_plan", "assets", "edit", "compose"]


@pytest.fixture()
def manifest() -> dict:
    return load_pipeline(PRODUCT_PROMO_PIPELINE)


def _brief() -> dict:
    return {
        "version": "1.0",
        "title": "White plantation shutters – 89mm louvres",
        "hook": "Light, your way.",
        "key_points": [
            "Made to measure for every window",
            "Louvre sizes 47mm, 63mm, 76mm and 89mm",
        ],
        "cta": "Book your free home survey",
        "tone": "warm, confident, British English",
        "style": "clean",
        "target_platform": "generic",
        "target_duration_seconds": 30,
        "metadata": {
            "videoType": "product_promo",
            "facts": {"options": [{"name": "Louvre size", "values": ["47mm", "63mm", "76mm", "89mm"]}]},
        },
    }


def _script() -> dict:
    return {
        "version": "1.0",
        "title": "Plantation shutters",
        "total_duration_seconds": 30,
        "sections": [
            {"id": "s1", "text": "Light, your way.", "start_seconds": 0, "end_seconds": 30}
        ],
    }


def test_manifest_has_the_koveriq_stage_order(manifest: dict) -> None:
    assert get_stage_order(manifest) == STAGES
    assert get_pipeline_stages(PRODUCT_PROMO_PIPELINE) == STAGES


def test_manifest_has_no_research_or_proposal_stage(manifest: dict) -> None:
    names = {stage["name"] for stage in manifest["stages"]}
    assert not names & {"research", "proposal"}


def test_no_stage_waits_for_a_human(manifest: dict) -> None:
    for stage in manifest["stages"]:
        assert stage["human_approval_default"] is False, stage["name"]


def test_revisions_are_capped_at_three(manifest: dict) -> None:
    assert manifest["orchestration"]["max_revisions_per_stage"] == 3


def test_agent_may_not_extend_the_pipeline(manifest: dict) -> None:
    assert manifest["extensions"] == {
        "custom_scripts": False,
        "custom_playbooks": False,
        "custom_skills": False,
        "custom_tools": False,
    }


def test_every_referenced_skill_exists(manifest: dict) -> None:
    refs = set(manifest["required_skills"]) | {s["skill"] for s in manifest["stages"]}
    for ref in refs:
        assert (REPO_ROOT / "skills" / f"{ref}.md").is_file(), ref


def test_prerequisites_accept_a_supplied_brief(tmp_path: Path) -> None:
    init_project("vid", title="Promo", pipeline_type=PRODUCT_PROMO_PIPELINE, pipeline_dir=tmp_path)
    write_brief_checkpoint(tmp_path, "vid", _brief(), user_id="u-123")

    # Does not raise: the only predecessor of `script` is the supplied brief.
    _enforce_stage_prerequisites(tmp_path, "vid", PRODUCT_PROMO_PIPELINE, "script", "completed")


def test_prerequisites_still_reject_a_missing_brief(tmp_path: Path) -> None:
    init_project("vid", title="Promo", pipeline_type=PRODUCT_PROMO_PIPELINE, pipeline_dir=tmp_path)

    with pytest.raises(CheckpointValidationError, match="PREREQUISITE VIOLATION"):
        _enforce_stage_prerequisites(tmp_path, "vid", PRODUCT_PROMO_PIPELINE, "script", "completed")


def test_brief_checkpoint_records_the_brief_preauth_policy(tmp_path: Path) -> None:
    init_project("vid", title="Promo", pipeline_type=PRODUCT_PROMO_PIPELINE, pipeline_dir=tmp_path)
    path = write_brief_checkpoint(tmp_path, "vid", _brief(), user_id="u-123")

    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    assert checkpoint["stage"] == "idea"
    assert checkpoint["status"] == "completed"
    assert checkpoint["human_approved"] is True
    assert checkpoint["metadata"]["approval_policy"] == APPROVAL_POLICY == "brief-preauth"
    assert checkpoint["metadata"]["approved_by"] == approver("u-123") == "koveriq:brief:u-123"
    assert checkpoint["artifacts"]["brief"]["metadata"]["approval_policy"] == "brief-preauth"

    log = json.loads((tmp_path / "vid" / "decision_log.json").read_text(encoding="utf-8"))
    by_category = {d["category"]: d for d in log["decisions"]}
    assert by_category["approval_policy"]["selected"] == "brief-preauth"
    runtime = by_category["render_runtime_selection"]
    assert runtime["selected"] == "hyperframes"
    assert {o["option_id"] for o in runtime["options_considered"]} >= {"hyperframes", "remotion"}


def test_brief_checkpoint_refuses_a_different_approval_policy(tmp_path: Path) -> None:
    init_project("vid", title="Promo", pipeline_type=PRODUCT_PROMO_PIPELINE, pipeline_dir=tmp_path)
    brief = _brief()
    brief["metadata"]["approval_policy"] = "interactive"

    with pytest.raises(ValueError, match="approval_policy"):
        write_brief_checkpoint(tmp_path, "vid", brief, user_id="u-123")


def test_brief_checkpoint_rejects_an_invalid_brief(tmp_path: Path) -> None:
    init_project("vid", title="Promo", pipeline_type=PRODUCT_PROMO_PIPELINE, pipeline_dir=tmp_path)
    brief = _brief()
    del brief["hook"]

    with pytest.raises(CheckpointValidationError):
        write_brief_checkpoint(tmp_path, "vid", brief, user_id="u-123")


def test_next_stage_checkpoint_writes_after_the_brief(tmp_path: Path) -> None:
    init_project("vid", title="Promo", pipeline_type=PRODUCT_PROMO_PIPELINE, pipeline_dir=tmp_path)
    write_brief_checkpoint(tmp_path, "vid", _brief(), user_id="u-123")

    path = write_stage_checkpoint(tmp_path, "vid", "script", {"script": _script()}, user_id="u-123")

    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    assert checkpoint["human_approved"] is True
    assert checkpoint["metadata"]["approved_by"] == "koveriq:brief:u-123"
