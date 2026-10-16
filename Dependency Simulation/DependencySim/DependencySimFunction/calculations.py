import csv
import io

from pydantic import BaseModel

HEADER = ["integer_1", "integer_2", "operand"]


class Calculation(BaseModel):
    line: int  # the row's line in the CSV, for error messages
    integer_1: int
    integer_2: int
    operand: str  # checked by evsim-calc, which owns the list of operands


def parse_calculations(csv_text: str) -> list[Calculation]:
    """Read the CSV into rows. Pure Python: no bucket, no library."""
    rows = csv.reader(io.StringIO(csv_text))
    header = [cell.strip() for cell in next(rows, [])]
    if header != HEADER:
        raise ValueError(f"The first line must be {','.join(HEADER)}, not {','.join(header)}")
    calculations = []
    for line, cells in enumerate(rows, start=2):
        if not any(cell.strip() for cell in cells):
            continue
        if len(cells) != 3:
            raise ValueError(f"Line {line}: expected 3 cells, got {len(cells)}")
        integer_1, integer_2, operand = (cell.strip() for cell in cells)
        try:
            calculations.append(Calculation(line=line, integer_1=int(integer_1), integer_2=int(integer_2), operand=operand))
        except ValueError:
            raise ValueError(f"Line {line}: {integer_1!r} and {integer_2!r} must both be integers") from None
    return calculations
