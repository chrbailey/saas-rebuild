#!/usr/bin/env python3
"""Run the validator shipped inside the saas-rebuild skill package."""

from pathlib import Path
import runpy
import sys


TARGET = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "saas-rebuild"
    / "tools"
    / "validate_artifacts.py"
)
sys.path.insert(0, str(TARGET.parent))
runpy.run_path(str(TARGET), run_name="__main__")
