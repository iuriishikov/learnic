from dataclasses import dataclass
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import (
    AccessWindow,
    ParticipantsLimit,
    StreamUrl,
    WebinarLessonsCount,
    WebinarSessionDuration,
)


@dataclass
class WebinarDetails(BaseEntity[ProductID]):
    """Webinar-specific defaults for a :class:`Product`.

    1:1 sub-entity of Product — its ``oid`` is the same UUID as the
    parent ``Product.oid``. Holds defaults applied to every cohort
    spawned from this webinar product (max participants, session
    duration, default streaming URL, access window before start,
    recording policy).
    """

    total_lessons: WebinarLessonsCount
    default_duration_minutes: WebinarSessionDuration
    allow_recording: bool
    default_max_participants: ParticipantsLimit | None = None
    default_stream_url: StreamUrl | None = None
    access_window_minutes: AccessWindow | None = None

    def change_lessons_count(self, new_count: WebinarLessonsCount) -> None:
        self.total_lessons = new_count

    def change_default_duration(
        self,
        new_duration: WebinarSessionDuration,
    ) -> None:
        self.default_duration_minutes = new_duration

    def change_default_max_participants(
        self,
        new_max: ParticipantsLimit | None,
    ) -> None:
        self.default_max_participants = new_max

    def change_default_stream_url(self, new_url: StreamUrl | None) -> None:
        self.default_stream_url = new_url

    def change_access_window(self, new_window: AccessWindow | None) -> None:
        self.access_window_minutes = new_window

    def set_recording(self, allowed: bool) -> None:
        self.allow_recording = allowed

    @classmethod
    def create(
        cls,
        product_id: ProductID,
        total_lessons: WebinarLessonsCount,
        default_duration_minutes: WebinarSessionDuration,
        allow_recording: bool,
        default_max_participants: ParticipantsLimit | None = None,
        default_stream_url: StreamUrl | None = None,
        access_window_minutes: AccessWindow | None = None,
    ) -> Self:
        return cls(
            oid=product_id,
            total_lessons=total_lessons,
            default_duration_minutes=default_duration_minutes,
            allow_recording=allow_recording,
            default_max_participants=default_max_participants,
            default_stream_url=default_stream_url,
            access_window_minutes=access_window_minutes,
        )
