import logging

from pydantic import BaseModel, Field, field_validator
from uipath.platform import UiPath

from sections import assign_sections, to_csv
from student_contract import Student

logger = logging.getLogger(__name__)

# ponytail: fixed paths, so every run overwrites the last one. Add a run id to the path when two
# runs must not collide.
SECTION_PATHS = ("output/section-1.csv", "output/section-2.csv")

_sdk: UiPath | None = None


def sdk() -> UiPath:
    # Created on first use, not at import: `uipath init` imports this file, and UiPath() needs a
    # login. Tests replace this function with a fake bucket.
    global _sdk
    if _sdk is None:
        _sdk = UiPath()
    return _sdk


# One input class for both operations, so every field but `operation` is optional.
class SectionsIn(BaseModel):
    operation: str  # "assign_sections" or "write_csvs", fixed per node in the Flow design
    students: list[Student] = Field(default_factory=list)  # assign_sections
    section_1: list[Student] = Field(default_factory=list)  # write_csvs
    section_2: list[Student] = Field(default_factory=list)  # write_csvs

    # A Flow node sends null for every input it doesn't set, and Pydantic rejects null for a list.
    @field_validator("students", "section_1", "section_2", mode="before")
    @classmethod
    def null_means_empty(cls, value):
        return [] if value is None else value


class SectionsOut(BaseModel):
    section_1: list[Student] = Field(default_factory=list)  # assign_sections
    section_2: list[Student] = Field(default_factory=list)  # assign_sections
    section_1_path: str | None = None  # write_csvs: the file's path inside the bucket
    section_2_path: str | None = None  # write_csvs


def _op_assign_sections(input: SectionsIn) -> SectionsOut:
    section_1, section_2 = assign_sections(input.students)
    return SectionsOut(section_1=section_1, section_2=section_2)


def _op_write_csvs(input: SectionsIn) -> SectionsOut:
    for path, students in zip(SECTION_PATHS, (input.section_1, input.section_2)):
        # The bucket name is written out here, not in a constant, so whoever reads bindings.json
        # can find the call it describes.
        sdk().buckets.upload(
            name="StudentSectionsFiles",
            blob_file_path=path,
            content=to_csv(students),
            content_type="text/csv",
        )
    return SectionsOut(section_1_path=SECTION_PATHS[0], section_2_path=SECTION_PATHS[1])


# One function per operation: each is what a @TaskProcessor class was.
OPERATIONS = {
    "assign_sections": _op_assign_sections,
    "write_csvs": _op_write_csvs,
}


def main(input: SectionsIn) -> SectionsOut:
    handler = OPERATIONS.get(input.operation)
    if handler is None:
        raise ValueError(
            f"Unknown operation {input.operation!r}; expected one of: {', '.join(OPERATIONS)}"
        )
    output = handler(input)
    logger.info(
        "%s: %d students in; sections of %d and %d",
        input.operation,
        len(input.students),
        len(output.section_1 or input.section_1),
        len(output.section_2 or input.section_2),
    )
    return output
