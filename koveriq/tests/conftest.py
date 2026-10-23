"""Shared test setup for the koveriq package."""

from __future__ import annotations

import hashlib

import pytest

from koveriq import vendor
from tests.conftest import (  # noqa: F401  (reuse the repo-wide no-network guard)
    _block_network,
    pytest_collection_modifyitems,
    pytest_configure,
)


@pytest.fixture(autouse=True)
def gsap_available(tmp_path_factory, monkeypatch):
    """Builds need the pinned gsap.min.js. Use it when it has been fetched;
    otherwise give the build a clearly fake stand-in so unit tests need no
    network. Lint/snapshot/render runs must use the real file."""
    try:
        vendor.verified_gsap()
        return
    except vendor.GsapUnavailable:
        pass
    stub = tmp_path_factory.mktemp("gsap") / "gsap.min.js"
    stub.write_bytes(b"/* test stand-in for gsap.min.js; not GSAP */ window.gsap = window.gsap || {};\n")
    monkeypatch.setenv("KOVERIQ_GSAP_JS", str(stub))
    monkeypatch.setattr(vendor, "GSAP_SHA256", hashlib.sha256(stub.read_bytes()).hexdigest())
