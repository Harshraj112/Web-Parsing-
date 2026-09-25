from typing import Any

from pydantic import BaseModel, Field


class JobPayload(BaseModel):
    title: str = Field(..., min_length=1)
    company: str = Field(default="")
    location: str = Field(default="")
    salary: str = Field(default="")
    source: str = Field(default="")
    link: str = Field(default="")
    confidence_score: int | None = None
    credibility_score: int | None = None
    posted_date: str | None = None
    scraped_at: str | None = None
    tags: str | None = None


class NotificationRequest(BaseModel):
    channel: str = Field(..., min_length=1)
    recipient: str = Field(..., min_length=1)
    message: str | None = None
    jobs: list[JobPayload] = Field(default_factory=list)


class NotificationResponse(BaseModel):
    success: bool
    channel: str
    message: str
    jobs_sent: int | None = None