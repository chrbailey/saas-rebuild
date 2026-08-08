"""Structural checks for the extraction-recipe research corpus.

These tests establish contract shape and bibliography integrity. They do not
establish that a URL is live, that its content supports a claim, or that a
route works in a particular tenant.
"""

from datetime import date
import json

import jsonschema
import pytest

from conftest import REPO_ROOT, SKILL_DIR

RECIPE_SCHEMA_PATH = SKILL_DIR / "templates" / "extraction-recipe.schema.json"
CORPUS_DIR = SKILL_DIR / "corpus"
RECIPES_DIR = CORPUS_DIR / "extraction-recipes"

RECIPES = sorted(RECIPES_DIR.glob("*.json")) if RECIPES_DIR.is_dir() else []


@pytest.fixture(scope="module")
def recipe_schema():
    return json.loads(RECIPE_SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def apps_index():
    data = json.loads((CORPUS_DIR / "apps.json").read_text())
    return {a["app"]: a for a in data["apps"]}


def test_apps_index_shape(apps_index):
    assert len(apps_index) == 100
    assert {entry["rank"] for entry in apps_index.values()} == set(range(1, 101))
    for slug, entry in apps_index.items():
        assert set(entry) == {"rank", "app", "app_name", "vendor", "category"}
        assert entry["app"] == slug
        assert entry["app_name"].strip()
        assert entry["vendor"].strip()
        assert entry["category"].strip()


def test_recipe_corpus_is_nonempty():
    assert RECIPES, "the research backlog is not recipe coverage"


@pytest.mark.parametrize(
    "path",
    [REPO_ROOT / "README.md", CORPUS_DIR / "README.md"],
    ids=["repository-readme", "corpus-readme"],
)
def test_documented_recipe_count_matches_corpus(path):
    assert f"v0.7, {len(RECIPES)}" in path.read_text()


def test_recipe_schema_itself_is_valid(recipe_schema):
    jsonschema.Draft202012Validator.check_schema(recipe_schema)


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: p.stem)
def test_recipe_validates(recipe_schema, path):
    jsonschema.validate(json.loads(path.read_text()), recipe_schema)


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: p.stem)
def test_recipe_matches_filename_and_index(apps_index, path):
    recipe = json.loads(path.read_text())
    assert recipe["app"] == path.stem, f"{path.name}: slug != filename"
    assert recipe["app"] in apps_index, f"{path.name}: not in apps.json"
    assert recipe["category"] == apps_index[recipe["app"]]["category"]


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: p.stem)
def test_recipe_bibliography_integrity(path):
    recipe = json.loads(path.read_text())
    urls = [source["url"] for source in recipe["sources"]]
    assert len(urls) == len(set(urls)), f"{path.name}: duplicate bibliography URL"
    tos_url = recipe["export_rights"]["tos_url"]
    if tos_url is not None:
        assert tos_url in urls, f"{path.name}: terms URL missing from bibliography"
    for s in recipe["sources"]:
        assert s["url"].startswith("https://"), (
            f"{path.name}: non-HTTPS source {s['url']!r}"
        )
        assert s["title"].strip()
        retrieved = date.fromisoformat(s["retrieved"])
        assert retrieved <= date.today(), f"{path.name}: future retrieval date"

    reviewed = date.fromisoformat(recipe["last_reviewed"])
    assert reviewed <= date.today(), f"{path.name}: future review date"
