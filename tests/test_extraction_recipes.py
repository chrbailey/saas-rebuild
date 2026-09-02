"""Structural checks for the extraction-recipe research corpus.

These tests establish contract shape and bibliography integrity. They do not
establish that a URL is live, that its content supports a claim, or that a
route works in a particular tenant.
"""

from datetime import date
import json
import re

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
    assert f"v0.8, {len(RECIPES)}" in path.read_text()


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


# Language that describes the research session rather than the vendor or the
# tenant. It belongs in research_caveats, never in reader-facing prose.
SESSION_PHRASES = (
    "research environment",
    "egress proxy",
    "task brief",
    "the tasking",
    "web-search budget",
    "websearch budget",
)


def string_leaves(value, path=()):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from string_leaves(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from string_leaves(item, path + (index,))


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: p.stem)
def test_recipe_prose_does_not_describe_the_research_session(path):
    recipe = json.loads(path.read_text())
    offenders = []
    for leaf_path, text in string_leaves(recipe):
        if leaf_path[:1] == ("research_caveats",):
            continue
        lowered = text.lower()
        for phrase in SESSION_PHRASES:
            if phrase in lowered:
                offenders.append(("/".join(map(str, leaf_path)), phrase))
    assert not offenders, f"{path.name}: move these into research_caveats: {offenders}"


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: p.stem)
def test_research_caveats_are_distinct_nonempty_sentences(path):
    recipe = json.loads(path.read_text())
    caveats = recipe.get("research_caveats", [])
    assert all(caveat.strip() == caveat and caveat for caveat in caveats), path.name
    assert len(caveats) == len(set(caveats)), f"{path.name}: duplicate caveat"
    for caveat in caveats:
        assert caveat.endswith("."), f"{path.name}: caveat should be a sentence: {caveat[:60]!r}"


def covered_applications_rows():
    text = (CORPUS_DIR / "README.md").read_text()
    section = text.split("## Covered applications", 1)[1]
    pattern = re.compile(
        r"^\| (?P<app_name>[^|]+?) \| \[`(?P<slug>[a-z0-9-]+)`\]\(extraction-recipes/(?P<file>[a-z0-9-]+)\.json\)"
        r" \| (?P<category>[^|]+?) \| (?P<verification>[^|]+?) \| (?P<last_reviewed>\d{4}-\d{2}-\d{2}) \|$",
        re.MULTILINE,
    )
    return [match.groupdict() for match in pattern.finditer(section)]


def test_covered_applications_table_lists_exactly_the_recipe_files():
    rows = covered_applications_rows()
    assert rows, "corpus README has no covered-applications table"
    slugs = [row["slug"] for row in rows]
    assert len(slugs) == len(set(slugs)), "duplicate rows"
    assert set(slugs) == {path.stem for path in RECIPES}
    for row in rows:
        assert row["slug"] == row["file"]
        recipe = json.loads((RECIPES_DIR / f"{row['slug']}.json").read_text())
        assert row["app_name"] == recipe["app_name"], row["slug"]
        assert row["category"] == recipe["category"], row["slug"]
        assert row["verification"] == recipe["verification"], row["slug"]
        assert row["last_reviewed"] == recipe["last_reviewed"], row["slug"]


def test_covered_applications_table_follows_backlog_rank(apps_index):
    ranks = [apps_index[row["slug"]]["rank"] for row in covered_applications_rows()]
    assert ranks == sorted(ranks)
