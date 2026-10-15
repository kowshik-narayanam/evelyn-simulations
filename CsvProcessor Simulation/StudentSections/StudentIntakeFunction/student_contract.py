"""The Student contract that StudentIntakeFlow sends to StudentSectionsFlow.

Each function project is packaged alone and can import only the files it ships, so this file is
copied into both StudentIntakeFunction and StudentSectionsFunction. A test in
StudentSectionsFunction fails if the two copies differ: edit one, then copy it over the other.
Isaac shares its contract the same way (isaac_contracts/models.py, three identical copies).
"""

from pydantic import BaseModel, ConfigDict, Field


class Student(BaseModel):
    # Strip spaces around every string before the length checks run, so "  " is rejected as blank.
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)  # "first-name surname"; sorting uses the first word
    id_number: str = Field(min_length=1)  # a string, so an ID like 007 keeps its zeros
    age: int = Field(ge=3, le=25)  # school age; "14" from a CSV cell is converted to 14
