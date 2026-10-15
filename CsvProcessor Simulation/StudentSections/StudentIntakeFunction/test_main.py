from pathlib import Path

import pytest

import main
from intake import parse_students
from main import IntakeIn

DATA = Path(__file__).parents[2] / "data" / "students.csv"


class FakeBuckets:
    """Stands in for sdk().buckets: "downloads" by copying a local file."""

    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def download(self, name, blob_file_path, destination_path):
        self.calls.append((name, blob_file_path))
        Path(destination_path).write_text(self.text, encoding="utf-8")


class FakeSdk:
    def __init__(self, text: str):
        self.buckets = FakeBuckets(text)


def test_the_data_file_parses_in_file_order():
    students = parse_students(DATA.read_text(encoding="utf-8"))
    assert len(students) == 20
    assert (students[0].name, students[0].id_number, students[0].age) == ("Zark Muckerberg", "STU-001", 15)
    assert students[-1].name == "John Appleseed"  # no sorting here: that is StudentSectionsFlow's job


def test_main_reads_the_bucket_file(monkeypatch):
    # A BOM, as Excel writes it, must not end up in the first header cell.
    fake = FakeSdk("\ufeff" + DATA.read_text(encoding="utf-8"))
    monkeypatch.setattr(main, "sdk", lambda: fake)
    output = main.main(IntakeIn())
    assert fake.buckets.calls == [("StudentSectionsFiles", "input/students.csv")]
    assert output.count == 20 and len(output.students) == 20


def test_blank_lines_and_spaces_are_ignored():
    students = parse_students("name,id_number,age\n\n  Bobby Tables , STU-1 , 14 \n\n")
    assert [(s.name, s.id_number, s.age) for s in students] == [("Bobby Tables", "STU-1", 14)]


@pytest.mark.parametrize(
    "csv_text, message",
    [
        pytest.param("name,age,id_number\nBobby Tables,14,STU-1\n", "The first line must be", id="wrong-header"),
        pytest.param("name,id_number,age\nBobby Tables,STU-1,40\n", "Line 2:", id="age-40"),
        pytest.param("name,id_number,age\nBobby Tables,STU-1,14\n ,STU-2,14\n", "Line 3:", id="blank-name"),
        pytest.param("name,id_number,age\nBobby Tables,STU-1\n", "Line 2: expected 3 cells", id="two-cells"),
    ],
)
def test_a_bad_file_fails_with_its_line_number(csv_text, message):
    with pytest.raises(ValueError, match=message):
        parse_students(csv_text)
