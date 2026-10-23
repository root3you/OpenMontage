"""Every style x format, with all ten kinds, passes `hyperframes lint` (0 errors).

Opt-in: needs Node and the pinned HyperFrames CLI in the npx cache.

    KOVERIQ_HF_LINT=1 pytest koveriq/tests/test_hyperframes_lint.py
"""

from __future__ import annotations

import os

import pytest

from koveriq import hyperframes
from koveriq.compose import FORMATS, STYLES, build_composition
from koveriq.scenes import KINDS
from koveriq.tests.fixtures import brand, make_assets, plan_for

pytestmark = pytest.mark.skipif(
    os.environ.get("KOVERIQ_HF_LINT") != "1" or not hyperframes.available(),
    reason="set KOVERIQ_HF_LINT=1 (needs node and the hyperframes CLI cache)",
)


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("fmt", sorted(FORMATS))
@pytest.mark.parametrize("logo", [False, True], ids=["wordmark", "logo"])
def test_all_kinds_lint_clean(tmp_path, style: str, fmt: str, logo: bool) -> None:
    plan, script, timings = plan_for(list(KINDS))
    result = build_composition(
        plan, script, timings, make_assets(tmp_path), style, fmt, brand(tmp_path, logo=logo), tmp_path / "comp"
    )
    report = hyperframes.lint(result.index_html.parent)
    assert report.errors == [], report.errors
    assert report.ok
    nested = [w for w in report.warnings if w.startswith("nested_structure_needs_subcomposition")]
    assert nested == []
