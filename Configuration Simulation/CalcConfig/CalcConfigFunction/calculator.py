"""The four calculators: what Evelyn's providers (Factiva, World-Check One, Firco) are to Evelyn.

Pure Python: no bucket and no asset. main.py fetches the numbers and the API key.
"""

import csv
import io
import operator
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ValidationError

HEADER = ["id", "a", "b"]

OPERATORS = {
    "ADD": operator.add,
    "SUBTRACT": operator.sub,
    "MULTIPLY": operator.mul,
    "DIVIDE": operator.truediv,
}


class Pair(BaseModel):
    id: str
    a: float
    b: float


class Result(BaseModel):
    id: str
    a: float
    b: float
    result: float | None  # None when b is 0 and DIVIDE_ON_ZERO is SKIP_ROW
    alert: bool
    note: str = ""


def parse_numbers(csv_text: str) -> list[Pair]:
    """The rows of a CSV with the header id,a,b. A bad row fails with its line number."""
    rows = csv.reader(io.StringIO(csv_text))
    header = [cell.strip() for cell in next(rows, [])]
    if header != HEADER:
        raise ValueError(f"The first line must be {','.join(HEADER)}, got {','.join(header)}")
    pairs = []
    for line, row in enumerate(rows, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(HEADER):
            raise ValueError(f"Line {line}: expected {len(HEADER)} cells, got {len(row)}")
        try:
            pairs.append(Pair(**dict(zip(HEADER, (cell.strip() for cell in row)))))
        except ValidationError as error:
            first = error.errors()[0]
            raise ValueError(f"Line {line}: {first['loc'][0]}: {first['msg']}") from None
    return pairs


def round_half_up(value: float, places: int) -> float:
    # Not round(): it rounds the binary value, so 2.01 / 2, printed 1.005, comes out 1.0.
    # Decimal(str(...)) rounds the number as it's printed, half up, as people expect.
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-int(places)), rounding=ROUND_HALF_UP))


def calculate(provider_id: str, pairs: list[Pair], config: dict) -> list[Result]:
    provider = config["provider"]
    alert_above = config["model"]["thresholds"]["alert_above"]
    results = []
    for pair in pairs:
        note = ""
        if provider_id == "DIVIDE" and pair.b == 0:
            policy = provider["DIVIDE_ON_ZERO"]
            if policy == "FAIL":
                raise ValueError(
                    f"{pair.id}: division by zero. Set provider.DIVIDE_ON_ZERO to SKIP_ROW or ZERO to carry on"
                )
            value, note = (None, "skipped: division by zero") if policy == "SKIP_ROW" else (0.0, "division by zero: 0")
        else:
            value = round_half_up(OPERATORS[provider_id](pair.a, pair.b), provider["ROUND_TO"])
        alert = value is not None and value > alert_above
        results.append(Result(id=pair.id, a=pair.a, b=pair.b, result=value, alert=alert, note=note))
    return results


def _text(number: float | None) -> str:
    if number is None:
        return ""
    return str(int(number)) if number == int(number) else str(number)


def to_csv(results: list[Result]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["id", "a", "b", "result", "alert", "note"])
    writer.writerows(
        [r.id, _text(r.a), _text(r.b), _text(r.result), "yes" if r.alert else "no", r.note] for r in results
    )
    return buffer.getvalue()
