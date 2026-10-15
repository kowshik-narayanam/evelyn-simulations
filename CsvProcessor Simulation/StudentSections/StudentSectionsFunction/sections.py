"""Sorting, splitting and CSV text. No bucket and no SDK here, so pytest can run it offline."""

import csv
import io

from student_contract import Student


def sort_key(student: Student) -> tuple[str, str, str]:
    first_name = student.name.split()[0]
    # casefold() makes "alice" sort first, before "Bobby". Plain sorting puts every capital letter
    # before every small one, so "alice" would land after "Zark".
    # Ties on the first name fall back to the full name, then the ID. The result never depends on
    # the order the rows arrived in.
    return (first_name.casefold(), student.name.casefold(), student.id_number)


def assign_sections(students: list[Student]) -> tuple[list[Student], list[Student]]:
    ordered = sorted(students, key=sort_key)
    half = (len(ordered) + 1) // 2  # section 1 takes the extra student when the count is odd
    return ordered[:half], ordered[half:]


def to_csv(students: list[Student]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["name", "id_number", "age"])  # the same columns as the input file
    writer.writerows([student.name, student.id_number, student.age] for student in students)
    return buffer.getvalue()
