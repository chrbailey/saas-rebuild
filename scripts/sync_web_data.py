#!/usr/bin/env python3
"""Sync canonical skill sources into web/data/ for the static web app.

The web app (web/) serves the saas-rebuild protocol from static files. This
script is the single source-of-truth bridge: it copies SKILL.md, the reference
playbooks, and the extraction-recipe corpus from skills/ into web/data/ and
generates a lightweight recipe index. Run it whenever the skill content
changes, then commit the result.

Usage: python scripts/sync_web_data.py
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "saas-rebuild"
XC_DIR = ROOT / "skills" / "export-compliance"
OUT = ROOT / "web" / "data"


def main() -> None:
    (OUT / "references").mkdir(parents=True, exist_ok=True)
    (OUT / "recipes").mkdir(parents=True, exist_ok=True)

    shutil.copyfile(SKILL_DIR / "SKILL.md", OUT / "skill.md")
    shutil.copyfile(XC_DIR / "SKILL.md", OUT / "export-compliance.md")

    for ref in (SKILL_DIR / "references").glob("*.md"):
        shutil.copyfile(ref, OUT / "references" / ref.name)

    index = []
    for recipe_path in sorted((SKILL_DIR / "corpus" / "extraction-recipes").glob("*.json")):
        recipe = json.loads(recipe_path.read_text())
        shutil.copyfile(recipe_path, OUT / "recipes" / recipe_path.name)
        index.append(
            {
                "app": recipe.get("app", recipe_path.stem),
                "app_name": recipe.get("app_name", recipe_path.stem),
                "vendor": recipe.get("vendor", ""),
                "category": recipe.get("category", ""),
                "routes": len(recipe.get("routes", [])),
            }
        )

    (OUT / "recipes" / "index.json").write_text(json.dumps(index, indent=2) + "\n")

    # Skill versions, so the web app can show which protocol version it serves
    # without hardcoding a number that goes stale at the next release.
    versions = json.loads((ROOT / "skill-versions.json").read_text())
    (OUT / "version.json").write_text(json.dumps(versions, indent=2, sort_keys=True) + "\n")

    print(f"Synced {len(index)} recipes, 2 skills, "
          f"{len(list((OUT / 'references').glob('*.md')))} references, "
          f"skill versions -> {OUT}")


if __name__ == "__main__":
    main()
