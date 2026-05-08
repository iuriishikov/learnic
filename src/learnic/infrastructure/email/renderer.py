from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from jinja2 import Environment, FileSystemLoader, select_autoescape

from learnic.application.common.email.components import (
    EmailButton,
    EmailComponent,
    EmailDivider,
    EmailGreeting,
    EmailHeading,
    EmailHeroImage,
    EmailInline,
    EmailLinkList,
    EmailParagraph,
    EmailVerificationCode,
    InlineBold,
    InlineLink,
    InlineText,
)
from learnic.infrastructure.email.constants import (
    BACKGROUND_COLOR,
    BORDER_COLOR,
    BRAND_COLOR,
    BRAND_NAME,
    COMPANY_ADDRESS,
    CONTENT_MAX_WIDTH_PX,
    FONT_FAMILY,
    LOGO_URL,
    MANAGE_PREFERENCES_URL,
    MUTED_TEXT_COLOR,
    PAGE_BACKGROUND_COLOR,
    TELEGRAM_ICON_URL,
    TELEGRAM_URL,
    TEXT_COLOR,
)

_TEMPLATES_DIR: Final = Path(__file__).parent / "templates"

_COMPONENT_TEMPLATES: Final[Mapping[type[EmailComponent], str]] = {
    EmailHeading: "components/heading.html.j2",
    EmailGreeting: "components/greeting.html.j2",
    EmailParagraph: "components/paragraph.html.j2",
    EmailButton: "components/button.html.j2",
    EmailVerificationCode: "components/verification_code.html.j2",
    EmailHeroImage: "components/hero_image.html.j2",
    EmailLinkList: "components/link_list.html.j2",
    EmailDivider: "components/divider.html.j2",
}


def build_environment() -> Environment:
    """Build the shared Jinja Environment used by :class:`EmailRenderer`.

    Templates are loaded from ``infrastructure/email/templates`` and HTML
    autoescape is enabled — every ``{{ value }}`` interpolation is XSS-safe
    by default; pre-rendered chunks are passed through ``| safe``.
    """
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )


class EmailRenderer:
    """Renders typed components into a branded HTML body and text alternative."""

    def __init__(self, env: Environment) -> None:
        self._env: Final = env

    def render_html(
        self,
        recipient: str,
        subject: str,
        components: Sequence[EmailComponent],
    ) -> str:
        body_html = "".join(self._render_component(c) for c in components)
        base = self._env.get_template("base.html.j2")
        return base.render(
            subject=subject,
            recipient=recipient,
            body_html=body_html,
            logo_url=LOGO_URL,
            brand_name=BRAND_NAME,
            brand_color=BRAND_COLOR,
            text_color=TEXT_COLOR,
            muted_text_color=MUTED_TEXT_COLOR,
            border_color=BORDER_COLOR,
            background_color=BACKGROUND_COLOR,
            page_background_color=PAGE_BACKGROUND_COLOR,
            content_max_width=CONTENT_MAX_WIDTH_PX,
            font_family=FONT_FAMILY,
            manage_preferences_url=MANAGE_PREFERENCES_URL,
            company_address=COMPANY_ADDRESS,
            telegram_url=TELEGRAM_URL,
            telegram_icon_url=TELEGRAM_ICON_URL,
            copyright_year=datetime.now(timezone.utc).year,
        )

    def render_text(self, components: Sequence[EmailComponent]) -> str:
        chunks = [self._component_text(c) for c in components]
        body = "\n\n".join(chunk for chunk in chunks if chunk)
        signature = f"С уважением,\nкоманда {BRAND_NAME}"
        return f"{body}\n\n{signature}" if body else signature

    def _render_component(self, component: EmailComponent) -> str:
        template_name = _COMPONENT_TEMPLATES[type(component)]
        template = self._env.get_template(template_name)
        return template.render(
            component=component,
            text_color=TEXT_COLOR,
            muted_text_color=MUTED_TEXT_COLOR,
            border_color=BORDER_COLOR,
            brand_color=BRAND_COLOR,
            font_family=FONT_FAMILY,
            content_max_width=CONTENT_MAX_WIDTH_PX,
        )

    @staticmethod
    def _component_text(component: EmailComponent) -> str:
        match component:
            case EmailHeading(text=text):
                return text
            case EmailGreeting(name=name):
                return f"Hi {name},"
            case EmailParagraph(parts=parts):
                return "".join(_inline_text(p) for p in parts)
            case EmailButton(label=label, url=url):
                return f"{label}: {url}"
            case EmailVerificationCode(code=code):
                return f"Your code: {code}"
            case EmailHeroImage():
                return ""
            case EmailLinkList(items=items):
                return "\n".join(
                    f"{item.title}: {item.url}\n  {item.description}" for item in items
                )
            case EmailDivider():
                return "---"


def _inline_text(part: EmailInline) -> str:
    match part:
        case InlineText(text=text) | InlineBold(text=text):
            return text
        case InlineLink(text=text, url=url):
            return f"{text} ({url})"
