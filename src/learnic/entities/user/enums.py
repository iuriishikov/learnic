from enum import StrEnum


class SocialLinkKind(StrEnum):
    """Recognised social-network kinds for a user's public profile.

    The enum keeps the kind list closed at the domain boundary so the
    frontend can ship per-kind icons / colors without guessing from URL
    patterns. ``OTHER`` is the escape hatch for less common platforms
    — the SPA renders a generic globe icon for it.
    """

    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    GITHUB = "github"
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    VK = "vk"
    DRIBBBLE = "dribbble"
    BEHANCE = "behance"
    OTHER = "other"
