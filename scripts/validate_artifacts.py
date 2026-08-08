#!/usr/bin/env python3
"""Run the validator shipped inside the saas-rebuild skill package."""

from pathlib import Path
import runpy


TARGET = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "saas-rebuild"
    / "tools"
    / "validate_artifacts.py"
)
runpy.run_path(str(TARGET), run_name="__main__")
