import csv
from pathlib import Path

import pytest

import main
from main import SectionsIn
from sections import assign_sections, sort_key, to_csv
from student_contract import Student

HERE = Path(__file__).parent
DATA = HERE.parents[1] / "data" / "students.csv"

SECTION_1 = [
    "alice Wonderland", "Bobby Tables", "Carol Singer", "Dack Jorsey", "Eve Dropper",
    "Foo Bar", "Gill Bates", "Jane Doe", "Jeve Stobs", "John Appleseed",
]
SECTION_2 = [
    "John Doe", "Lorem Ipsum", "Mallory Middleman", "Melon Eusk", "Natya Sadella",
    "Parry Lage", "Pundar Sichai", "Rennis Ditchie", "Tinus Lorvalds", "Zark Muckerberg",
]


def _students_from_data_file() -> list[Student]:
    # Read the file with the csv module, not with StudentIntakeFunction's parser: that one lives in
    # the other project, which this project can't import.
    with DATA.open(encoding="utf-8") as file:
        return [Student(**row) for row in csv.DictReader(file)]


def test_the_two_contract_copies_are_identical():
    # Each project ships its own copy. If they drift, the Flows still pass JSON along, but one side
    # accepts what the other rejects.
    intake_copy = HERE.parent / "StudentIntakeFunction" / "student_contract.py"
    assert (HERE / "student_contract.py").read_bytes() == intake_copy.read_bytes(), (
        "student_contract.py differs between the two functions: copy the edited one over the other"
    )


def test_the_twenty_students_split_into_the_expected_sections():
    section_1, section_2 = assign_sections(_students_from_data_file())
    assert [s.name for s in section_1] == SECTION_1
    assert [s.name for s in section_2] == SECTION_2


def test_the_input_file_is_jumbled():
    # Guards the data, not the code: if someone reorders the CSV into an easy order, a broken
    # sort could still pass the test above.
    students = _students_from_data_file()
    position = {s.id_number: rank for rank, s in enumerate(sorted(students, key=sort_key))}
    ranks = [position[s.id_number] for s in students]
    assert ranks != sorted(ranks) and ranks != sorted(ranks, reverse=True)
    # No two neighbours in the file are neighbours once sorted.
    assert all(abs(a - b) >= 2 for a, b in zip(ranks, ranks[1:]))
    # The first ten rows hold five students from each section.
    assert sum(rank < 10 for rank in ranks[:10]) == 5
    # The tie at the boundary: John Doe has the lower ID and comes first in the file, so sorting
    # by ID or keeping file order would put the wrong John in section 1.
    names = [s.name for s in students]
    assert names.index("John Doe") < names.index("John Appleseed")


def test_plain_sorting_would_get_the_sections_wrong():
    # Why sort_key uses casefold(): without it, "alice" goes after "Zark" and changes sections.
    students = _students_from_data_file()
    plain = sorted(students, key=lambda s: s.name)
    assert [s.name for s in plain[:10]] != SECTION_1


def test_an_odd_count_puts_the_extra_student_in_section_1():
    students = [Student(name=f"Name{i} X", id_number=f"S{i}", age=14) for i in range(21)]
    section_1, section_2 = assign_sections(students)
    assert (len(section_1), len(section_2)) == (11, 10)


def test_csv_text_has_the_input_columns():
    text = to_csv([Student(name="Bobby Tables", id_number="STU-017", age=14)])
    assert text == "name,id_number,age\nBobby Tables,STU-017,14\n"


class FakeBuckets:
    def __init__(self):
        self.files = {}

    def upload(self, name, blob_file_path, content, content_type):
        assert name == "StudentSectionsFiles" and content_type == "text/csv"
        self.files[blob_file_path] = content


class FakeSdk:
    def __init__(self):
        self.buckets = FakeBuckets()


def test_write_csvs_uploads_both_sections(monkeypatch):
    fake = FakeSdk()
    monkeypatch.setattr(main, "sdk", lambda: fake)
    section_1, section_2 = assign_sections(_students_from_data_file())
    output = main.main(SectionsIn(operation="write_csvs", section_1=section_1, section_2=section_2))
    assert (output.section_1_path, output.section_2_path) == main.SECTION_PATHS
    assert fake.buckets.files["output/section-1.csv"].splitlines()[1] == "alice Wonderland,STU-010,13"
    assert fake.buckets.files["output/section-2.csv"].splitlines()[-1] == "Zark Muckerberg,STU-001,15"


def test_a_flow_node_sends_null_for_inputs_it_does_not_set():
    output = main.main(
        SectionsIn(operation="assign_sections", students=[], section_1=None, section_2=None)
    )
    assert output.section_1 == [] and output.section_2 == []


def test_an_unknown_operation_fails():
    with pytest.raises(ValueError, match="Unknown operation"):
        main.main(SectionsIn(operation="sort"))
