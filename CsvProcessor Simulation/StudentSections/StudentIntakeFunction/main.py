import logging
import tempfile
from pathlib import Path

from pydantic import BaseModel
from uipath.platform import UiPath

from intake import parse_students
from student_contract import Student

logger = logging.getLogger(__name__)

_sdk: UiPath | None = None


def sdk() -> UiPath:
    # Created on first use, not at import: `uipath init` imports this file, and UiPath() needs a
    # login. Tests replace this function with a fake bucket.
    global _sdk
    if _sdk is None:
        _sdk = UiPath()
    return _sdk


class IntakeIn(BaseModel):
    csv_path: str = "input/students.csv"  # the file's path inside the bucket


class IntakeOut(BaseModel):
    students: list[Student]  # what StudentIntakeFlow hands to StudentSectionsFlow
    count: int


def main(input: IntakeIn) -> IntakeOut:
    with tempfile.TemporaryDirectory() as folder:
        local_file = Path(folder) / "students.csv"
        # The bucket name is written out here, not in a constant: `uipath init --infer-bindings`
        # reads this call and writes the bucket into bindings.json, which is how the Solution
        # learns that this function uses the bucket.
        sdk().buckets.download(
            name="StudentSectionsFiles",
            blob_file_path=input.csv_path,
            destination_path=str(local_file),
        )
        csv_text = local_file.read_text(encoding="utf-8-sig")  # -sig drops the BOM Excel writes
    students = parse_students(csv_text)
    logger.info("Parsed %d students from %s", len(students), input.csv_path)
    return IntakeOut(students=students, count=len(students))
