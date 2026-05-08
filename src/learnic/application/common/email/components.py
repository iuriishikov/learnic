"""Typed email components rendered into HTML by the infrastructure layer.

Handlers and tasks build a list of these dataclasses instead of writing
HTML strings; the :class:`EmailService` adapter takes care of turning the
list into a styled, email-client-safe message.
"""

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True, slots=True)
class InlineText:
    """Plain text inside a paragraph."""

    text: str


@dataclass(frozen=True, slots=True)
class InlineBold:
    """Bold text inside a paragraph."""

    text: str


@dataclass(frozen=True, slots=True)
class InlineLink:
    """Hyperlink inside a paragraph."""

    text: str
    url: str


EmailInline = Union[InlineText, InlineBold, InlineLink]


@dataclass(frozen=True, slots=True)
class EmailHeading:
    """Large heading rendered as an ``<h1>`` near the top of the body."""

    text: str


@dataclass(frozen=True, slots=True)
class EmailGreeting:
    """Greeting line such as ``Hi {name},``."""

    name: str


@dataclass(frozen=True, slots=True)
class EmailParagraph:
    """Body paragraph composed of inline parts (text/bold/link)."""

    parts: tuple[EmailInline, ...]

    @classmethod
    def text(cls, value: str) -> "EmailParagraph":
        """Build a paragraph containing a single :class:`InlineText`."""
        return cls((InlineText(value),))


@dataclass(frozen=True, slots=True)
class EmailButton:
    """Primary call-to-action button with a label and URL."""

    label: str
    url: str


@dataclass(frozen=True, slots=True)
class EmailVerificationCode:
    """Numeric verification code rendered as boxed digits."""

    code: str


@dataclass(frozen=True, slots=True)
class EmailHeroImage:
    """Wide hero image at the top of the email body."""

    url: str
    alt: str


@dataclass(frozen=True, slots=True)
class EmailLinkListItem:
    """Single entry in an :class:`EmailLinkList`."""

    title: str
    url: str
    description: str


@dataclass(frozen=True, slots=True)
class EmailLinkList:
    """Vertical list of titled links with descriptions (welcome digests)."""

    items: tuple[EmailLinkListItem, ...]


@dataclass(frozen=True, slots=True)
class EmailDivider:
    """Horizontal divider between body sections."""


EmailComponent = Union[
    EmailHeading,
    EmailGreeting,
    EmailParagraph,
    EmailButton,
    EmailVerificationCode,
    EmailHeroImage,
    EmailLinkList,
    EmailDivider,
]
