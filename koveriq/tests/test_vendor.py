"""koveriq.vendor: GSAP is fetched and verified, never trusted blindly."""

from __future__ import annotations

import hashlib
import io
import tarfile

import pytest

from koveriq import vendor


def _tarball(content: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("package/dist/gsap.min.js")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def test_tarball_with_the_wrong_integrity_is_refused() -> None:
    with pytest.raises(vendor.GsapUnavailable, match="integrity"):
        vendor.extract_gsap(_tarball(b"window.gsap = {};"))


def test_extracted_file_is_checked_against_the_pinned_sha256(monkeypatch) -> None:
    tarball = _tarball(b"window.gsap = {};")
    digest = __import__("base64").b64encode(hashlib.sha512(tarball).digest()).decode()
    monkeypatch.setattr(vendor, "GSAP_TARBALL_INTEGRITY", f"sha512-{digest}")
    with pytest.raises(vendor.GsapUnavailable, match="sha256"):
        vendor.extract_gsap(tarball)
    monkeypatch.setattr(vendor, "GSAP_SHA256", hashlib.sha256(b"window.gsap = {};").hexdigest())
    assert vendor.extract_gsap(tarball) == b"window.gsap = {};"


def test_missing_file_explains_how_to_fetch(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KOVERIQ_GSAP_JS", str(tmp_path / "nope.js"))
    with pytest.raises(vendor.GsapUnavailable, match="koveriq.vendor fetch"):
        vendor.verified_gsap()


def test_tampered_file_is_refused(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "gsap.min.js"
    fake.write_bytes(b"alert('not gsap')")
    monkeypatch.setenv("KOVERIQ_GSAP_JS", str(fake))
    monkeypatch.setattr(vendor, "GSAP_SHA256", "0" * 64)
    with pytest.raises(vendor.GsapUnavailable, match="mismatch"):
        vendor.verified_gsap()


def test_default_location_follows_xdg_cache_home(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("KOVERIQ_GSAP_JS", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert vendor.gsap_path() == tmp_path / "koveriq" / f"gsap-{vendor.GSAP_VERSION}" / "gsap.min.js"


def test_build_refuses_without_gsap(tmp_path, monkeypatch) -> None:
    from koveriq.compose import CompositionError, build_composition
    from koveriq.tests.fixtures import brand, make_assets, plan_for

    monkeypatch.setenv("KOVERIQ_GSAP_JS", str(tmp_path / "missing.js"))
    plan, script, timings = plan_for(["text_card", "cta_endcard"])
    with pytest.raises(CompositionError, match="gsap"):
        build_composition(plan, script, timings, make_assets(tmp_path), "clean", "16:9", brand(), tmp_path / "c")
