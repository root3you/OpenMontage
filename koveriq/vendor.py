"""GSAP, fetched and verified instead of committed.

HyperFrames compositions animate with GSAP, which is under GreenSock's
"Standard 'no charge' license" (not an open-source licence, no express
redistribution right). So this public AGPL fork does not ship GSAP. The image
build (and `make koveriq-vendor` locally) fetches the pinned npm tarball,
checks its npm integrity, extracts `dist/gsap.min.js` and checks its sha256.
Every composition gets a byte-identical copy, so renders never reach a CDN.

    python -m koveriq.vendor fetch [dest]   # needs network once
    python -m koveriq.vendor path           # where builds look for it

Builds look for the file at `$KOVERIQ_GSAP_JS`, else
`$XDG_CACHE_HOME/koveriq/gsap-<version>/gsap.min.js` (default `~/.cache`).
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

GSAP_VERSION = "3.14.2"
GSAP_TARBALL_URL = f"https://registry.npmjs.org/gsap/-/gsap-{GSAP_VERSION}.tgz"
GSAP_TARBALL_INTEGRITY = "sha512-P8/mMxVLU7o4+55+1TCnQrPmgjPKnwkzkXOK1asnR9Jg2lna4tEY5qBJjMmAaOBDDZWtlRjBXjLa0w53G/uBLA=="
GSAP_SHA256 = "c174bfce53a729418d57a8ad8625e7247c793a22fef8e2851e3cfa3de9cd8280"


class GsapUnavailable(RuntimeError):
    """The pinned gsap.min.js is missing or does not match its hash."""


def default_gsap_path() -> Path:
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return cache / "koveriq" / f"gsap-{GSAP_VERSION}" / "gsap.min.js"


def gsap_path() -> Path:
    configured = os.environ.get("KOVERIQ_GSAP_JS")
    return Path(configured) if configured else default_gsap_path()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verified_gsap() -> bytes:
    """The bytes of the pinned gsap.min.js, or GsapUnavailable."""
    path = gsap_path()
    if not path.is_file():
        raise GsapUnavailable(
            f"gsap.min.js {GSAP_VERSION} not found at {path}. Run `python -m koveriq.vendor fetch` "
            "(or `make koveriq-vendor`) once, or set KOVERIQ_GSAP_JS."
        )
    data = path.read_bytes()
    if _sha256(data) != GSAP_SHA256:
        raise GsapUnavailable(f"{path} is not gsap.min.js {GSAP_VERSION} (sha256 mismatch)")
    return data


def extract_gsap(tarball: bytes) -> bytes:
    """Check the npm integrity of a gsap tarball and return dist/gsap.min.js."""
    algo, _, expected = GSAP_TARBALL_INTEGRITY.partition("-")
    actual = base64.b64encode(hashlib.new(algo, tarball).digest()).decode()
    if actual != expected:
        raise GsapUnavailable("gsap tarball does not match its npm integrity hash")
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
        member = archive.extractfile("package/dist/gsap.min.js")
        if member is None:
            raise GsapUnavailable("gsap tarball has no package/dist/gsap.min.js")
        data = member.read()
    if _sha256(data) != GSAP_SHA256:
        raise GsapUnavailable("gsap.min.js in the tarball does not match the pinned sha256")
    return data


def fetch_gsap(dest: Path | None = None) -> Path:  # pragma: no cover - network
    dest = dest or gsap_path()
    with urllib.request.urlopen(GSAP_TARBALL_URL, timeout=60) as response:
        data = extract_gsap(response.read())
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest


def main(argv: list[str]) -> int:  # pragma: no cover - CLI
    if argv[:1] == ["fetch"]:
        dest = Path(argv[1]) if len(argv) > 1 else None
        path = fetch_gsap(dest)
        print(f"gsap {GSAP_VERSION} -> {path}")
        return 0
    if argv[:1] == ["path"]:
        print(gsap_path())
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
