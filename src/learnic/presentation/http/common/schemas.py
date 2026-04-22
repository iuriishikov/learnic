"""Schemas shared between multiple routers at the HTTP boundary."""

from uuid import UUID

from pydantic import BaseModel


class FileSchema(BaseModel):
    """Reference to a file resource.

    Returned whenever an endpoint produces or owns a file — avatar and
    cover uploads today, course banners, message attachments, etc. in
    the future. Start with just the identifier; grow with extra fields
    (URL, MIME, size) as concrete endpoints need them.
    """

    oid: UUID
