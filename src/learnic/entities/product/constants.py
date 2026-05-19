from typing import Final

TITLE_MAX_LEN: Final = 200
DESCRIPTION_MAX_LEN: Final = 50_000

QA_QUESTION_MAX_LEN: Final = 500
QA_ANSWER_MAX_LEN: Final = 5_000

DURATION_HOURS_MIN: Final = 1
DURATION_HOURS_MAX: Final = 10_000

WEBINAR_LESSONS_MIN: Final = 1
WEBINAR_LESSONS_MAX: Final = 1_000

WEBINAR_PARTICIPANTS_MIN: Final = 1

WEBINAR_DURATION_MINUTES_MIN: Final = 1
WEBINAR_DURATION_MINUTES_MAX: Final = 24 * 60

ACCESS_WINDOW_MINUTES_MIN: Final = 0
ACCESS_WINDOW_MINUTES_MAX: Final = 7 * 24 * 60

STREAM_URL_MAX_LEN: Final = 2048

# Product price bounds (in minor units of currency — kopecks for RUB).
# Wire and storage use minor units; UI converts to/from major units
# (1 RUB == 100 kopecks). Upper bound = 50 000 RUB.
PRICE_AMOUNT_MIN: Final = 0
PRICE_AMOUNT_MAX: Final = 50_000 * 100
