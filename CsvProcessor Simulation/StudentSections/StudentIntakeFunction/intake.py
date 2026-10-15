"""CSV text in, Student objects out. No bucket and no SDK here, so pytest can run it offline."""

import csv
import io

from pydantic import ValidationError

from student_contract import Student

HEADER = ["name", "id_number", "age"]


def parse_students(csv_text: str) -> list[Student]:
    reader = csv.reader(io.StringIO(csv_text))
    header = [cell.strip() for cell in next(reader, [])]
    if header != HEADER:
        raise ValueError(f"The first line must be {','.join(HEADER)}, got {','.join(header)!r}")

    students = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue  # a blank line, e.g. the empty last line some editors add
        # reader.line_num is the line in the file, so an error points at the row to fix.
        if len(row) != len(HEADER):
            raise ValueError(f"Line {reader.line_num}: expected 3 cells, got {len(row)}")
        try:
            students.append(Student(**dict(zip(HEADER, row))))
        except ValidationError as error:
            # One bad row fails the whole file: the job fails and StudentSectionsFlow never starts.
            raise ValueError(f"Line {reader.line_num}: {error}") from error
    return students
