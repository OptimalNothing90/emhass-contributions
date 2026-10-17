"""Shared fixtures for the skills test suite.

The helper scripts are plain files (no package), so they are imported by path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SCHEMA_DIR = SKILLS_DIR / "emhass-config-validate" / "schema" / "v0.18.6"


def load_script(skill: str, script: str):
    """Import ``skills/<skill>/scripts/<script>`` as a module."""
    path = SKILLS_DIR / skill / "scripts" / script
    name = f"skill_{skill.replace('-', '_')}_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def schema_dir() -> Path:
    return SCHEMA_DIR


@pytest.fixture(scope="session")
def config_defaults() -> dict:
    return json.loads((SCHEMA_DIR / "config_defaults.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def validate_config_mod():
    return load_script("emhass-config-validate", "validate_config.py")


@pytest.fixture(scope="session")
def explain_plan_mod():
    return load_script("emhass-plan-explain", "explain_plan.py")


@pytest.fixture(scope="session")
def scan_logs_mod():
    return load_script("emhass-anomaly", "scan_logs.py")
