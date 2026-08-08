"""The extraction-recipe corpus: every recipe validates against the
recipe schema, matches its filename and an apps.json entry, and carries
real citations. Coverage is reported by the corpus itself (apps.json is
the target list); these tests guard correctness of what exists, not
completeness of what doesn't yet."""

import json

import jsonschema
import pytest

from conftest import SKILL_DIR

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
    for slug, entry in apps_index.items():
        assert set(entry) == {"rank", "app", "app_name", "vendor", "category"}
        assert entry["app"] == slug


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
def test_recipe_sources_are_http_urls(path):
    recipe = json.loads(path.read_text())
    for s in recipe["sources"]:
        assert s["url"].startswith("http"), f"{path.name}: non-URL source {s['url']!r}"
