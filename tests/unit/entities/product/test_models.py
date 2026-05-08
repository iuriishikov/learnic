import uuid

from learnic.entities.file.ids import FileID
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
)
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import (
    DurationHours,
    ProductDescription,
    ProductTitle,
    WebinarLessonsCount,
    WebinarSessionDuration,
)
from learnic.entities.user.models import UserID


def _author() -> UserID:
    return UserID(uuid.uuid4())


def _course() -> Product:
    return Product.create_course(
        author_id=_author(),
        name=ProductTitle("X"),
        description=ProductDescription("<p>X</p>"),
        total_duration_in_hours=DurationHours(10),
    )


def _webinar() -> Product:
    return Product.create_webinar(
        author_id=_author(),
        name=ProductTitle("W"),
        description=ProductDescription("<p>W</p>"),
        total_duration_in_hours=DurationHours(8),
        total_lessons=WebinarLessonsCount(4),
        default_duration_minutes=WebinarSessionDuration(90),
        allow_recording=True,
    )


class TestNameOnlyDrafts:
    def test_create_course_name_only(self) -> None:
        p = Product.create_course(
            author_id=_author(),
            name=ProductTitle("Draft"),
        )
        assert p.description is None
        assert p.total_duration_in_hours is None
        assert p.cover_file_id is None
        assert p.webinar_details is None

    def test_create_webinar_name_only(self) -> None:
        p = Product.create_webinar(
            author_id=_author(),
            name=ProductTitle("Draft"),
        )
        assert p.description is None
        assert p.total_duration_in_hours is None
        assert p.webinar_details is None

    def test_create_webinar_partial_defaults_skips_details(self) -> None:
        # Two of three required defaults — webinar_details stays None.
        p = Product.create_webinar(
            author_id=_author(),
            name=ProductTitle("Draft"),
            total_lessons=WebinarLessonsCount(4),
            default_duration_minutes=WebinarSessionDuration(90),
        )
        assert p.webinar_details is None

    def test_attach_webinar_details(self) -> None:
        p = Product.create_webinar(
            author_id=_author(),
            name=ProductTitle("Draft"),
        )
        from learnic.entities.product.webinar_details import WebinarDetails

        details = WebinarDetails.create(
            product_id=p.oid,
            total_lessons=WebinarLessonsCount(8),
            default_duration_minutes=WebinarSessionDuration(60),
            allow_recording=False,
        )
        p.attach_webinar_details(details)
        assert p.webinar_details is details


class TestCreateCourse:
    def test_initial_state(self) -> None:
        p = _course()
        assert p.type is ProductType.COURSE
        assert p.status is ProductStatus.DRAFT
        assert p.published_at is None
        assert p.webinar_details is None

    def test_unique_oids(self) -> None:
        a, b = _course(), _course()
        assert a.oid != b.oid


class TestCreateWebinar:
    def test_initial_state(self) -> None:
        p = _webinar()
        assert p.type is ProductType.WEBINAR
        assert p.webinar_details is not None
        assert p.webinar_details.oid == p.oid
        assert p.webinar_details.total_lessons.value == 4


class TestPublishArchive:
    def test_publish_sets_status_and_timestamp(self) -> None:
        p = _course()
        p.publish()
        assert p.status is ProductStatus.PUBLISHED
        assert p.published_at is not None

    def test_publish_idempotent(self) -> None:
        p = _course()
        p.publish()
        first = p.published_at
        p.publish()
        assert p.published_at == first

    def test_archive_sets_status(self) -> None:
        p = _course()
        p.archive()
        assert p.status is ProductStatus.ARCHIVED

    def test_unarchive_draft_returns_to_draft(self) -> None:
        p = _course()
        p.archive()
        p.unarchive()
        assert p.status is ProductStatus.DRAFT

    def test_unarchive_previously_published_returns_to_published(self) -> None:
        p = _course()
        p.publish()
        p.archive()
        p.unarchive()
        assert p.status is ProductStatus.PUBLISHED


class TestMutators:
    def test_rename(self) -> None:
        p = _course()
        p.rename(ProductTitle("New name"))
        assert p.name.value == "New name"


class TestCover:
    def test_create_course_without_cover(self) -> None:
        p = _course()
        assert p.cover_file_id is None

    def test_create_course_with_cover(self) -> None:
        cover = FileID(uuid.uuid4())
        p = Product.create_course(
            author_id=_author(),
            name=ProductTitle("With cover"),
            description=ProductDescription("<p>x</p>"),
            total_duration_in_hours=DurationHours(10),
            cover_file_id=cover,
        )
        assert p.cover_file_id == cover

    def test_set_cover_returns_previous(self) -> None:
        p = _course()
        first = FileID(uuid.uuid4())
        second = FileID(uuid.uuid4())
        assert p.set_cover(first) is None
        assert p.cover_file_id == first
        assert p.set_cover(second) == first
        assert p.cover_file_id == second

    def test_remove_cover_returns_previous_and_clears(self) -> None:
        p = _course()
        cover = FileID(uuid.uuid4())
        p.set_cover(cover)
        assert p.remove_cover() == cover
        assert p.cover_file_id is None
