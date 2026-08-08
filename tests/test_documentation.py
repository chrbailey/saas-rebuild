"""Documentation links and high-risk public statements stay reviewable."""

import re

from conftest import REPO_ROOT


def test_relative_markdown_links_resolve():
    missing = []
    for path in sorted(REPO_ROOT.rglob("*.md")):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target or re.match(r"^[a-z]+:", target):
                continue
            if not (path.parent / target).exists():
                missing.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    assert not missing, f"broken relative Markdown links: {missing}"


def test_retired_overclaims_do_not_return():
    paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "skills" / "saas-rebuild" / "SKILL.md",
        REPO_ROOT / "skills" / "saas-rebuild" / "references" / "extraction-playbook.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
    retired = [
        "raw tenant data never leaves",
        "empty table = unused module",
        "0.3%-populated custom field = abandoned experiment",
        "the delta from vanilla is the requirements list",
        "behavioral equivalence on historical data is the only proof",
    ]
    assert not [claim for claim in retired if claim in text]
