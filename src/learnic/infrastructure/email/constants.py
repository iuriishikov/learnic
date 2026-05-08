"""Static brand assets and links for rendered emails."""

from typing import Final

BRAND_COLOR: Final = "#887aeb"
BRAND_COLOR_HOVER: Final = "#6c5ce7"
BRAND_NAME: Final = "Learnic"

TEXT_COLOR: Final = "#111827"
MUTED_TEXT_COLOR: Final = "#6b7280"
BORDER_COLOR: Final = "#e5e7eb"
BACKGROUND_COLOR: Final = "#ffffff"
PAGE_BACKGROUND_COLOR: Final = "#f5f5f7"

CONTENT_MAX_WIDTH_PX: Final = 560
FONT_FAMILY: Final = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "Helvetica, Arial, sans-serif"
)

CONTENT_BASE_URL: Final = "https://s3.regru.cloud/learnic-content"

LOGO_S3_KEY: Final = "branding/email/logo.png"
TELEGRAM_ICON_S3_KEY: Final = "branding/email/telegram.png"

LOGO_URL: Final = f"{CONTENT_BASE_URL}/{LOGO_S3_KEY}"
TELEGRAM_ICON_URL: Final = f"{CONTENT_BASE_URL}/{TELEGRAM_ICON_S3_KEY}"

MANAGE_PREFERENCES_URL: Final = "https://learnic.ru/settings/notifications"
COMPANY_ADDRESS: Final = "Learnic, Россия, Москва"
TELEGRAM_URL: Final = "https://t.me/learnic_ru"
