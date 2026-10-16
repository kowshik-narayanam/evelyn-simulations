import hashlib
import json
import tomllib
from importlib.metadata import distribution
from pathlib import Path

import evsim_calc
import pytest

import main
from calculations import parse_calculations
from main import CalculateIn

HERE = Path(__file__).parent
DATA = HERE.parents[1] / "data" / "calculations.csv"
WHEEL = HERE / "wheels" / "evsim_calc-1.0.0-py3-none-any.whl"

# One result per row of data/calculations.csv. Rows 8 and 9 are the Java division trap:
# -7 divide 2 is -3 in Java (and in evsim-calc), -4 with Python's //.
EXPECTED = [42, 3, 42, -7, 42, -100, 21, -3, -3, 0]


class FakeBuckets:
    """Stands in for sdk().buckets: "downloads" by writing the given text."""

    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def download(self, name, blob_file_path, destination_path):
        self.calls.append((name, blob_file_path))
        Path(destination_path).write_text(self.text, encoding="utf-8")


class FakeSdk:
    def __init__(self, text: str):
        self.buckets = FakeBuckets(text)


def run(monkeypatch, csv_text):
    fake = FakeSdk(csv_text)
    monkeypatch.setattr(main, "sdk", lambda: fake)
    return main.main(CalculateIn()), fake


def test_the_ten_rows_give_the_expected_results(monkeypatch):
    output, fake = run(monkeypatch, "﻿" + DATA.read_text(encoding="utf-8"))  # with a BOM, as Excel writes
    assert fake.buckets.calls == [("DependencySimFiles", "input/calculations.csv")]
    assert [r.result for r in output.results] == EXPECTED
    assert output.count == 10
    assert output.library_version == "1.0.0"


def test_the_data_keeps_the_java_division_trap():
    rows = parse_calculations(DATA.read_text(encoding="utf-8"))
    assert len(rows) == 10
    assert {(r.integer_1, r.integer_2, r.operand) for r in rows} >= {(-7, 2, "divide"), (7, -2, "divide")}
    assert {r.operand for r in rows} == set(evsim_calc.OPERANDS)  # every operand is used


def test_the_library_is_installed_from_the_vendored_wheel():
    # Imported from the project's .venv, and put there from wheels/, not from the library's source.
    assert "site-packages" in Path(evsim_calc.__file__).parts
    direct_url = json.loads(distribution("evsim-calc").read_text("direct_url.json"))
    assert direct_url["url"].endswith("/wheels/evsim_calc-1.0.0-py3-none-any.whl")


def test_uv_lock_pins_the_wheel_in_this_folder():
    # The lock records the wheel's sha256, the way Maven checks a jar's checksum. A rebuilt wheel
    # that wasn't re-locked fails here before it fails on the tenant.
    lock = tomllib.loads((HERE / "uv.lock").read_text())
    package = next(p for p in lock["package"] if p["name"] == "evsim-calc")
    assert package["version"] == "1.0.0"
    assert package["source"] == {"path": "wheels/evsim_calc-1.0.0-py3-none-any.whl"}
    assert package["wheels"][0]["hash"] == "sha256:" + hashlib.sha256(WHEEL.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "csv_text, message",
    [
        pytest.param("operand,integer_1,integer_2\nadd,1,2\n", "The first line must be", id="wrong-header"),
        pytest.param("integer_1,integer_2,operand\n1,2\n", "Line 2: expected 3 cells", id="two-cells"),
        pytest.param("integer_1,integer_2,operand\n1,2,add\n1.5,2,add\n", "Line 3: '1.5' and '2' must both be integers", id="not-an-integer"),
        pytest.param("integer_1,integer_2,operand\n2,3,power\n", "Line 2: unknown operand 'power'", id="unknown-operand"),
        pytest.param("integer_1,integer_2,operand\n9,0,divide\n", "Line 2: 9 divide 0: division by zero", id="divide-by-zero"),
    ],
)
def test_a_bad_row_fails_with_its_line_number(monkeypatch, csv_text, message):
    with pytest.raises(ValueError, match=message):
        run(monkeypatch, csv_text)


def test_blank_lines_and_spaces_are_ignored():
    rows = parse_calculations("integer_1,integer_2,operand\n\n  4 , 2 , divide \n\n")
    assert [(r.line, r.integer_1, r.integer_2, r.operand) for r in rows] == [(3, 4, 2, "divide")]
