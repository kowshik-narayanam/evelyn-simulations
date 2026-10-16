"""The worker's settings: Evelyn's configuration.json and configuration_payload.json, at toy size.

configuration.json is the form: each setting's key, label, type, allowed values and default. It
ships inside this package, as Evelyn's form ships inside its package.

Three layers; a later one wins, key by key:
1. the form's defaults;
2. the saved payload in the bucket, holding only what an administrator changed;
3. the run's own overrides, from the Flow's input.

Every value is checked against the form, so a typo fails the run here and names itself.
Pure Python: no bucket. main.py does the downloading.
"""

import json
from datetime import date
from pathlib import Path

FORM = json.loads((Path(__file__).parent / "configuration.json").read_text(encoding="utf-8"))
FIELDS = {field["key"]: field for field in FORM["fields"]}


def flatten(nested: dict, prefix: str = "") -> dict:
    """{"provider": {"ROUND_TO": 2}} becomes {"provider.ROUND_TO": 2}, the form's key style."""
    flat = {}
    for key, value in nested.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, path + "."))
        else:
            flat[path] = value
    return flat


def unflatten(flat: dict) -> dict:
    nested: dict = {}
    for path, value in flat.items():
        *parents, leaf = path.split(".")
        node = nested
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return nested


def check(key: str, value):
    """value, if the form allows it for key. Otherwise a ValueError that names the key."""
    field = FIELDS.get(key)
    if field is None:
        raise ValueError(f"Unknown setting {key!r}. Known settings: {', '.join(FIELDS)}")
    kind = field["type"]
    if kind in ("radio", "select"):  # Evelyn's form uses both for "pick one"
        allowed = [option["value"] for option in field["values"]]
        if value not in allowed:
            raise ValueError(f"{key} is {value!r}; allowed: {', '.join(allowed)}")
    elif kind == "number":
        rules = field["validate"]
        # bool is an int in Python: true must not pass as 1.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a number, got {value!r}")
        if rules.get("integer") and value != int(value):
            raise ValueError(f"{key} must be a whole number, got {value}")
        if not rules["min"] <= value <= rules["max"]:
            raise ValueError(f"{key} is {value}; allowed: {rules['min']} to {rules['max']}")
    elif kind == "checkbox":
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false, got {value!r}")
    elif kind == "textfield":
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be some text, got {value!r}")
    else:
        raise ValueError(f"configuration.json: {key} has an unknown type {kind!r}")
    return value


def load(saved: dict | None, overrides: dict | None) -> dict:
    """The three layers merged and checked, as a nested dict with every setting present."""
    values = {key: field["defaultValue"] for key, field in FIELDS.items()}
    for layer in (saved, overrides):
        for key, value in flatten(layer or {}).items():
            values[key] = check(key, value)
    return unflatten(values)


def report_path(config: dict, today: date) -> str:
    """Where the CSV report goes: resulting_path with {year} and {month} filled in. "" when it's off."""
    if not config["configuration"]["reports"]["csv"]["enable"]:
        return ""
    # replace, not str.format: an administrator types this path, and format() would crash on any
    # other {…} in it.
    folder = (
        config["configuration"]["resulting_path"]
        .replace("{year}", f"{today.year:04d}")
        .replace("{month}", f"{today.month:02d}")
    )
    # ponytail: a fixed file name, so each run overwrites the month's last report. Add the run's id
    # when two runs in one month must keep both.
    return folder.rstrip("/") + "/calculation-report.csv"
