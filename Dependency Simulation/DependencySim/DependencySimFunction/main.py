import logging
import tempfile
from pathlib import Path

import evsim_calc
from pydantic import BaseModel
from uipath.platform import UiPath

from calculations import Calculation, parse_calculations

logger = logging.getLogger(__name__)

_sdk: UiPath | None = None


def sdk() -> UiPath:
    # Created on first use, not at import: `uipath init` imports this file, and UiPath() needs a
    # login. Tests replace this function with a fake bucket.
    global _sdk
    if _sdk is None:
        _sdk = UiPath()
    return _sdk


class CalculateIn(BaseModel):
    csv_path: str = "input/calculations.csv"  # the file's path inside the bucket


class Result(Calculation):
    result: int  # what evsim-calc returned


class CalculateOut(BaseModel):
    results: list[Result]
    count: int
    library_version: str  # the evsim-calc this job imported: proof of which wheel shipped


def main(input: CalculateIn) -> CalculateOut:
    with tempfile.TemporaryDirectory() as folder:
        local_file = Path(folder) / "calculations.csv"
        sdk().buckets.download(
            name="DependencySimFiles",
            blob_file_path=input.csv_path,
            destination_path=str(local_file),
        )
        csv_text = local_file.read_text(encoding="utf-8-sig")  # -sig drops the BOM Excel writes
    results = []
    for row in parse_calculations(csv_text):
        try:
            value = evsim_calc.calculate(row.integer_1, row.integer_2, row.operand)
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError(f"Line {row.line}: {error}") from error
        results.append(Result(**row.model_dump(), result=value))
    logger.info("evsim-calc %s calculated %d rows from %s", evsim_calc.__version__, len(results), input.csv_path)
    return CalculateOut(results=results, count=len(results), library_version=evsim_calc.__version__)
