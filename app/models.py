"""Request/response models for ApplyTrack.

Pydantic (bundled with FastAPI) handles validation: missing company or
role is a 422, an unknown status is a 422, a malformed date is a 422.
The API layer never has to hand-check those cases.

NOTE: this module imports the ``datetime`` module (not ``from datetime
import date``) on purpose. ``OutreachCreate`` has a field named
``date`` whose type is also ``date`` — writing ``date: date | None``
fails in plain Python, because inside a class body the annotation
``date`` resolves to the field itself (whose value is None) instead
of ``datetime.date``. Spelling the type as ``datetime.date`` avoids
the collision entirely.
"""

import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Status(str, Enum):
    APPLIED = "Applied"
    OA = "OA/Assessment"
    INTERVIEW = "Interview"
    OFFER = "Offer"
    REJECTED = "Rejected"


class Channel(str, Enum):
    EMAIL = "Email"
    LINKEDIN = "LinkedIn"
    PHONE = "Phone"
    OTHER = "Other"


def _blank_to_none(value: str | None) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class ApplicationCreate(BaseModel):
    company: str = Field(..., min_length=1, max_length=120)
    role: str = Field(..., min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=120)
    term: str | None = Field(default=None, max_length=60)
    req_id: str | None = Field(default=None, max_length=60)
    date_applied: datetime.date | None = None
    status: Status = Status.APPLIED
    deadline: datetime.date | None = None
    pay: str | None = Field(default=None, max_length=60)
    notes: str | None = None
    link: str | None = Field(default=None, max_length=500)

    @field_validator("company", "role", mode="before")
    @classmethod
    def _strip_required(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("location", "term", "req_id", "pay", "notes", "link",
                     mode="before")
    @classmethod
    def _strip_optional(cls, v):
        return _blank_to_none(v)

    @field_validator("link")
    @classmethod
    def _link_must_be_http(cls, v):
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("link must start with http:// or https://")
        return v


class ApplicationOut(ApplicationCreate):
    """An application as stored, plus its id and outreach count."""

    id: int
    outreach_count: int = 0


class OutreachCreate(BaseModel):
    contact_name: str = Field(..., min_length=1, max_length=120)
    date: datetime.date | None = None  # defaults to today
    channel: Channel = Channel.EMAIL
    notes: str | None = None

    @field_validator("contact_name", mode="before")
    @classmethod
    def _strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("notes", mode="before")
    @classmethod
    def _strip_notes(cls, v):
        return _blank_to_none(v)


class OutreachOut(OutreachCreate):
    id: int
    application_id: int
    date: datetime.date
