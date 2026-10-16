import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from uipath.platform import UiPath

import settings
from calculator import Pair, Result, calculate, parse_numbers, to_csv

logger = logging.getLogger(__name__)

# The bucket this function reads and writes, and where the saved settings live in it.
# bindings.json declares the bucket and the Credential asset by hand (README step 6):
# `uipath init` doesn't find them in the code.
BUCKET = "CalcConfigFiles"
CONFIG_PATH = "config/configuration_payload.json"

_sdk: UiPath | None = None


def sdk() -> UiPath:
    # Created on first use, not at import: `uipath init` imports this file, and UiPath() needs a
    # login. Tests replace this function with a fake.
    global _sdk
    if _sdk is None:
        _sdk = UiPath()
    return _sdk


# One input class for every operation, so every field but `operation` is optional.
class CalcIn(BaseModel):
    operation: str  # fixed per node in the Flow: see OPERATIONS
    overrides: dict = Field(default_factory=dict)  # load_configuration: this run's settings (layer 3)
    config_path: str = CONFIG_PATH  # load_configuration: the saved payload in the bucket (layer 2)
    config: dict | None = None  # read_numbers and the calculators: Load configuration's output.config
    numbers: list[Pair] = Field(default_factory=list)  # read_numbers when INPUT_TYPE is API; the calculators
    results: list[Result] = Field(default_factory=list)  # write_report
    report_path: str = ""  # write_report

    # A Flow node sends every input, set or not. `uip maestro flow node add` writes the unset ones
    # into the .flow as null (lists, objects) or "" (strings). Both mean "the default".
    @field_validator("overrides", mode="before")
    @classmethod
    def null_means_no_overrides(cls, value):
        return {} if value is None else value

    @field_validator("numbers", "results", mode="before")
    @classmethod
    def null_means_no_rows(cls, value):
        return [] if value is None else value

    @field_validator("config_path", mode="before")
    @classmethod
    def blank_means_the_default_path(cls, value):
        return value or CONFIG_PATH

    @field_validator("report_path", mode="before")
    @classmethod
    def null_means_no_path(cls, value):
        return value or ""


class CalcOut(BaseModel):
    config: dict | None = None  # load_configuration: all three layers, merged and checked
    input_type: str = ""  # load_configuration, read_numbers
    provider_id: str = ""  # load_configuration: the Switch reads it. The calculators echo theirs
    report_enabled: bool = False  # load_configuration: the Decision reads it
    report_path: str = ""  # load_configuration ("" when the report is off), write_report
    overridden_keys: list[str] = Field(default_factory=list)  # load_configuration
    numbers: list[Pair] = Field(default_factory=list)  # read_numbers
    count: int = 0  # read_numbers
    results: list[Result] = Field(default_factory=list)  # the calculators
    alert_count: int = 0  # the calculators
    rows_written: int = 0  # write_report


def _download_text(path: str) -> str:
    with tempfile.TemporaryDirectory() as folder:
        local_file = Path(folder) / "download"
        sdk().buckets.download(name=BUCKET, blob_file_path=path, destination_path=str(local_file))
        return local_file.read_text(encoding="utf-8-sig")  # -sig drops the BOM Excel writes


def _op_load_configuration(input: CalcIn) -> CalcOut:
    # No fallback to the defaults when the file is missing: a run that silently calculates with
    # the defaults is worse than a run that fails.
    saved = json.loads(_download_text(input.config_path))
    config = settings.load(saved, input.overrides)
    path = settings.report_path(config, datetime.now(timezone.utc).date())
    logger.info("Configuration in force: %s", json.dumps(config))
    return CalcOut(
        config=config,
        input_type=config["configuration"]["INPUT_TYPE"],
        provider_id=config["configuration"]["PROVIDER_ID"],
        report_enabled=bool(path),
        report_path=path,
        overridden_keys=list(settings.flatten(input.overrides)),
    )


def _config(input: CalcIn) -> dict:
    if input.config is None:
        raise ValueError(f"{input.operation} needs config: map it to Load configuration's output.config")
    # Checked again, cheaply: a node fed a hand-typed object instead of Load configuration's
    # output fails here, not halfway through a calculation.
    return settings.load(input.config, None)


def _op_read_numbers(input: CalcIn) -> CalcOut:
    config = _config(input)
    input_type = config["configuration"]["INPUT_TYPE"]
    if input_type == "CSV":
        numbers = parse_numbers(_download_text(config["configuration"]["DATA_FILE_LOCATION"]))
    else:  # API: the numbers came with the run, in the trigger's input
        numbers = input.numbers
    return CalcOut(input_type=input_type, numbers=numbers, count=len(numbers))


def _check_api_key(config: dict) -> None:
    # Evelyn keeps provider credentials in its configuration. Here the configuration names only
    # the asset; the secret stays in Orchestrator and never reaches an output or a log.
    name = config["provider"]["API_KEY_ASSET"]
    try:
        key = sdk().assets.retrieve_credential(name)
    except Exception as error:
        raise ValueError(f"Couldn't read the Credential asset {name!r}: {error}") from error
    if not key:
        raise ValueError(f"The Credential asset {name!r} has no password: set one on the tenant")
    logger.info("API key from the Credential asset %s: present (value not logged)", name)


def _calculator(provider_id: str):
    def run(input: CalcIn) -> CalcOut:
        config = _config(input)
        configured = config["configuration"]["PROVIDER_ID"]
        if configured != provider_id:
            raise ValueError(
                f"This node calculates {provider_id}, but configuration.PROVIDER_ID is {configured}: "
                "check the Switch's case for this node"
            )
        # ponytail: the toy calls no service, so it only checks the key exists. A real provider
        # node would send it with each request.
        _check_api_key(config)
        results = calculate(provider_id, input.numbers, config)
        return CalcOut(provider_id=provider_id, results=results, alert_count=sum(r.alert for r in results))

    return run


def _op_write_report(input: CalcIn) -> CalcOut:
    if not input.report_path:
        raise ValueError("write_report needs report_path: map it to Load configuration's output.report_path")
    sdk().buckets.upload(
        name=BUCKET,
        blob_file_path=input.report_path,
        content=to_csv(input.results),
        content_type="text/csv",
    )
    return CalcOut(report_path=input.report_path, rows_written=len(input.results))


# One function per operation: each is what a @TaskProcessor class was. The four calculators are
# one node each in the Flow, chosen by the Switch.
OPERATIONS = {
    "load_configuration": _op_load_configuration,
    "read_numbers": _op_read_numbers,
    "add": _calculator("ADD"),
    "subtract": _calculator("SUBTRACT"),
    "multiply": _calculator("MULTIPLY"),
    "divide": _calculator("DIVIDE"),
    "write_report": _op_write_report,
}


def main(input: CalcIn) -> CalcOut:
    handler = OPERATIONS.get(input.operation)
    if handler is None:
        raise ValueError(f"Unknown operation {input.operation!r}; expected one of: {', '.join(OPERATIONS)}")
    return handler(input)
