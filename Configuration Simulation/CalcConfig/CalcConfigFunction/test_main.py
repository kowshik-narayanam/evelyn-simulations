import json
from datetime import date
from pathlib import Path

import pytest

import main
import settings
from calculator import calculate, parse_numbers, round_half_up, to_csv
from main import CalcIn

HERE = Path(__file__).parent
DATA = HERE.parents[1] / "data"
NUMBERS = (DATA / "numbers.csv").read_text(encoding="utf-8")
PAYLOAD = json.loads((DATA / "configuration_payload.json").read_text(encoding="utf-8"))

# What each calculator returns for data/numbers.csv with the defaults (ROUND_TO 2, alert above 100)
# and DIVIDE_ON_ZERO SKIP_ROW. N-04 checks the rounding, N-05 divides by zero, N-07 sits on the
# alert threshold without crossing it.
EXPECTED = {
    "ADD": [252, 21, -5, 4.01, 42, 4, 52],
    "SUBTRACT": [248, 3, -10, 0.01, 42, -2, 48],
    "MULTIPLY": [500, 108, -18.75, 4.02, 0, 3, 100],
    "DIVIDE": [125, 1.33, -3, 1.01, None, 0.33, 25],
}
ALERTS = {"ADD": 1, "SUBTRACT": 1, "MULTIPLY": 2, "DIVIDE": 1}


def _config(**overrides) -> dict:
    return settings.load(PAYLOAD, overrides)


# --- the form and the three layers -------------------------------------------------------------


def test_every_default_in_the_form_passes_its_own_check():
    for key, field in settings.FIELDS.items():
        settings.check(key, field["defaultValue"])


def test_no_payload_and_no_overrides_gives_the_form_defaults():
    config = settings.load(None, None)
    assert config["configuration"]["INPUT_TYPE"] == "CSV"
    assert config["configuration"]["PROVIDER_ID"] == "ADD"
    assert config["provider"] == {"DIVIDE_ON_ZERO": "FAIL", "ROUND_TO": 2, "API_KEY_ASSET": "CalcApiKey"}


def test_the_saved_payload_wins_over_the_defaults_key_by_key():
    config = settings.load(PAYLOAD, None)
    assert config["configuration"]["PROVIDER_ID"] == "DIVIDE"
    assert config["provider"]["DIVIDE_ON_ZERO"] == "SKIP_ROW"
    assert config["provider"]["ROUND_TO"] == 2  # not in the payload: the form's default


def test_the_run_overrides_win_over_the_saved_payload():
    config = settings.load(PAYLOAD, {"configuration": {"PROVIDER_ID": "MULTIPLY"}})
    assert config["configuration"]["PROVIDER_ID"] == "MULTIPLY"
    assert config["configuration"]["INPUT_TYPE"] == "CSV"  # still the payload's


@pytest.mark.parametrize(
    "overrides, message",
    [
        pytest.param({"configuration": {"PROVIDER_ID": "DIVDE"}}, "allowed: ADD, SUBTRACT", id="typo-in-a-value"),
        pytest.param({"provider": {"ROUND_TOO": 3}}, "Unknown setting 'provider.ROUND_TOO'", id="typo-in-a-key"),
        pytest.param({"provider": {"ROUND_TO": 9}}, "allowed: 0 to 6", id="out-of-range"),
        pytest.param({"provider": {"ROUND_TO": 2.5}}, "whole number", id="not-whole"),
        pytest.param({"provider": {"ROUND_TO": True}}, "must be a number", id="bool-is-not-a-number"),
        pytest.param({"configuration": {"reports": {"csv": {"enable": "yes"}}}}, "true or false", id="checkbox"),
        pytest.param({"configuration": {"resulting_path": " "}}, "some text", id="blank-text"),
    ],
)
def test_a_bad_setting_fails_and_names_itself(overrides, message):
    with pytest.raises(ValueError, match=message):
        settings.load(PAYLOAD, overrides)


def test_the_report_path_fills_in_the_month():
    assert settings.report_path(_config(), date(2026, 3, 9)) == "output/2026/03/calculation-report.csv"


def test_no_report_path_when_the_report_is_off():
    config = _config(configuration={"reports": {"csv": {"enable": False}}})
    assert settings.report_path(config, date(2026, 3, 9)) == ""


# --- the calculators ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider_id", list(EXPECTED))
def test_each_calculator_on_the_data_file(provider_id):
    results = calculate(provider_id, parse_numbers(NUMBERS), _config())
    assert [r.result for r in results] == EXPECTED[provider_id]
    assert sum(r.alert for r in results) == ALERTS[provider_id]


def test_rounding_is_half_up_on_the_printed_number():
    # round(2.01 / 2, 2) is 1.0: the float is 1.00499999…
    assert round_half_up(2.01 / 2, 2) == 1.01
    assert round_half_up(-2.5, 0) == -3


@pytest.mark.parametrize(
    "policy, result, note",
    [("SKIP_ROW", None, "skipped: division by zero"), ("ZERO", 0, "division by zero: 0")],
)
def test_dividing_by_zero_follows_the_setting(policy, result, note):
    [row] = calculate("DIVIDE", parse_numbers("id,a,b\nZ,42,0\n"), _config(provider={"DIVIDE_ON_ZERO": policy}))
    assert (row.result, row.note) == (result, note)


def test_dividing_by_zero_fails_by_default():
    with pytest.raises(ValueError, match="N-05: division by zero"):
        calculate("DIVIDE", parse_numbers(NUMBERS), settings.load(None, None))


@pytest.mark.parametrize(
    "csv_text, message",
    [
        pytest.param("a,b,id\n1,2,X\n", "The first line must be id,a,b", id="wrong-header"),
        pytest.param("id,a,b\nX,1,two\n", "Line 2: b:", id="not-a-number"),
        pytest.param("id,a,b\nX,1\n", "Line 2: expected 3 cells", id="two-cells"),
    ],
)
def test_a_bad_numbers_file_fails_with_its_line_number(csv_text, message):
    with pytest.raises(ValueError, match=message):
        parse_numbers(csv_text)


def test_the_report_csv():
    results = calculate("DIVIDE", parse_numbers("id,a,b\nA,250,2\nB,42,0\n"), _config())
    assert to_csv(results) == "id,a,b,result,alert,note\nA,250,2,125,yes,\nB,42,0,,no,skipped: division by zero\n"


# --- main.py: what each Flow node does, with a fake bucket and a fake asset ---------------------


class FakeSdk:
    def __init__(self, files: dict, api_key: str | None = "fake-key"):
        self.buckets = self
        self.assets = self
        self.files = files
        self.api_key = api_key
        self.uploads = {}

    def download(self, name, blob_file_path, destination_path):
        assert name == "CalcConfigFiles"
        Path(destination_path).write_text(self.files[blob_file_path], encoding="utf-8")

    def upload(self, name, blob_file_path, content, content_type):
        assert name == "CalcConfigFiles" and content_type == "text/csv"
        self.uploads[blob_file_path] = content

    def retrieve_credential(self, name):
        assert name == "CalcApiKey"
        return self.api_key


@pytest.fixture
def fake(monkeypatch):
    fake = FakeSdk({main.CONFIG_PATH: json.dumps(PAYLOAD), "input/numbers.csv": NUMBERS})
    monkeypatch.setattr(main, "sdk", lambda: fake)
    return fake


def test_the_nodes_in_order_as_the_flow_runs_them(fake):
    # Inputs the node doesn't set arrive as null or "", as `node add` writes them.
    loaded = main.main(CalcIn(operation="load_configuration", overrides=None, config_path=""))
    assert (loaded.provider_id, loaded.input_type, loaded.report_enabled) == ("DIVIDE", "CSV", True)
    numbers = main.main(CalcIn(operation="read_numbers", config=loaded.config, numbers=None))
    assert numbers.count == 7
    divided = main.main(CalcIn(operation="divide", config=loaded.config, numbers=numbers.numbers))
    assert ([r.result for r in divided.results], divided.alert_count) == (EXPECTED["DIVIDE"], 1)
    written = main.main(CalcIn(operation="write_report", results=divided.results, report_path=loaded.report_path))
    assert written.rows_written == 7
    assert fake.uploads[loaded.report_path].splitlines()[1] == "N-01,250,2,125,yes,"


def test_api_input_uses_the_numbers_from_the_run(fake):
    config = _config(configuration={"INPUT_TYPE": "API"})
    out = main.main(CalcIn(operation="read_numbers", config=config, numbers=[{"id": "R1", "a": 1, "b": 2}]))
    assert (out.input_type, out.count) == ("API", 1)


def test_the_overridden_keys_are_listed(fake):
    out = main.main(CalcIn(operation="load_configuration", overrides={"configuration": {"PROVIDER_ID": "ADD"}}))
    assert (out.provider_id, out.overridden_keys) == ("ADD", ["configuration.PROVIDER_ID"])


def test_a_calculator_node_refuses_the_wrong_provider(fake):
    with pytest.raises(ValueError, match="This node calculates ADD, but configuration.PROVIDER_ID is DIVIDE"):
        main.main(CalcIn(operation="add", config=_config(), numbers=[]))


def test_a_calculator_needs_the_api_key(fake):
    fake.api_key = ""
    with pytest.raises(ValueError, match="'CalcApiKey' has no password"):
        main.main(CalcIn(operation="divide", config=_config(), numbers=[]))


def test_a_calculator_needs_the_configuration(fake):
    with pytest.raises(ValueError, match="divide needs config"):
        main.main(CalcIn(operation="divide", config=None))


def test_an_unknown_operation_fails():
    with pytest.raises(ValueError, match="Unknown operation"):
        main.main(CalcIn(operation="modulo"))
