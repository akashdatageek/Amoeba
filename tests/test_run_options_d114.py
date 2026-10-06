"""D114 — context size as run options: max_input_chars and max_summary_input_chars are whitelisted with ranges in
adapt.yaml (kept by D117 for in-task edits); a value inside the range passes validation, a value outside is a V2
violation."""

from amoeba.adapt.recipe import Edit, Recipe, adapt_config, apply_edit, validate_recipe


def with_option(name, value):
    return apply_edit(Recipe(family="calc"), Edit(op="set_run_option", params={"name": name, "value": value}))


def test_whitelisted_with_ranges():
    ro = adapt_config()["recipe"]["run_options"]
    assert ro["max_input_chars"] == {"min": 3000, "max": 20000}
    assert ro["max_summary_input_chars"] == {"min": 15000, "max": 60000}
    assert validate_recipe(with_option("max_input_chars", 12000)) == []
    assert validate_recipe(with_option("max_summary_input_chars", 45000)) == []
    for name, bad in (("max_input_chars", 100), ("max_input_chars", 50000), ("max_summary_input_chars", "lots")):
        [v] = validate_recipe(with_option(name, bad))
        assert v.rule == "V2", (name, bad)

