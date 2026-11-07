import importlib

import pytest


@pytest.mark.parametrize("name", ["data", "engine", "strategies", "validation", "api"])
def test_subpackage_imports(name: str) -> None:
    importlib.import_module(f"backtest_lab.{name}")
