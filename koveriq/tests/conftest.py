"""Reuse the repository-wide test safety net: no test may open a network socket."""

from tests.conftest import (  # noqa: F401  (pytest discovers fixtures and hooks by name)
    _block_network,
    pytest_collection_modifyitems,
    pytest_configure,
)
