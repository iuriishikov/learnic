from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from learnic.infrastructure.configs import Configs, load_configs
from learnic.infrastructure.persistence.models.cohort import (
    map_cohort_table,
    map_webinar_schedule_table,
    map_webinar_session_table,
)
from learnic.infrastructure.persistence.models.course_enrollment import (
    map_course_enrollment_table,
)
from learnic.infrastructure.persistence.models.course_lesson import (
    map_course_lesson_table,
)
from learnic.infrastructure.persistence.models.course_module import (
    map_course_module_table,
)
from learnic.infrastructure.persistence.models.course_release import (
    map_course_release_table,
)
from learnic.infrastructure.persistence.models.file import map_file_table
from learnic.infrastructure.persistence.models.product import (
    map_product_qa_table,
    map_product_table,
    map_webinar_details_table,
)
from learnic.infrastructure.persistence.models.notification import (
    map_notification_table,
)
from learnic.infrastructure.persistence.models.push_subscription import (
    map_push_subscription_table,
)
from learnic.infrastructure.persistence.models.product_collaboration import (
    map_collaboration_grant_table,
    map_product_collaboration_table,
)
from learnic.infrastructure.persistence.models.role import map_role_table
from learnic.infrastructure.persistence.models.user import map_user_table
from learnic.infrastructure.persistence.models.user_experience import (
    map_user_experience_table,
)
from learnic.infrastructure.persistence.models.user_social_link import (
    map_user_social_link_table,
)
from learnic.infrastructure.persistence.models.webinar_enrollment import (
    map_webinar_enrollment_table,
)
from learnic.presentation.http.routes.auth import router as auth_router
from learnic.presentation.http.routes.cohort import (
    router as cohort_router,
)
from learnic.presentation.http.routes.course_content import (
    router as course_content_router,
)
from learnic.presentation.http.routes.course_enrollment import (
    me_router as my_course_enrollments_router,
    router as course_enrollment_router,
)
from learnic.presentation.http.routes.course_release import (
    router as course_release_router,
    student_router as course_student_content_router,
)
from learnic.presentation.http.routes.presence import (
    router as presence_router,
)
from learnic.presentation.http.routes.product import (
    course_router as product_course_router,
    router as product_router,
)
from learnic.presentation.http.routes.product_collaboration import (
    collab_router as collaboration_router,
    me_router as my_collaborations_router,
    product_router as product_collaboration_router,
)
from learnic.presentation.http.routes.notification import (
    router as notification_router,
)
from learnic.presentation.http.routes.notification_preferences import (
    router as notification_preferences_router,
)
from learnic.presentation.http.routes.push import (
    me_router as push_me_router,
    public_router as push_public_router,
)
from learnic.presentation.http.routes.auth_ws import (
    router as auth_ws_router,
)
from learnic.presentation.http.routes.notification_ws import (
    router as notification_ws_router,
)
from learnic.presentation.http.routes.product_qa import (
    router as product_qa_router,
)
from learnic.presentation.http.routes.role import (
    role_router as standalone_role_router,
    router as product_roles_router,
)
from learnic.presentation.http.routes.product_ws import (
    router as product_ws_router,
)
from learnic.presentation.http.routes.root import router as root_router
from learnic.presentation.http.routes.webinar_enrollment import (
    me_router as my_webinar_enrollments_router,
    router as webinar_enrollment_router,
)
from learnic.presentation.http.routes.webinar_schedule import (
    router as webinar_schedule_router,
)
from learnic.presentation.http.routes.webinar_session import (
    router as webinar_session_router,
)
from learnic.presentation.http.routes.user import router as user_router
from learnic.presentation.http.routes.user_experience import (
    me_router as my_user_experiences_router,
    router as user_experiences_router,
)
from learnic.presentation.http.routes.user_social_link import (
    me_router as my_user_social_links_router,
    router as user_social_links_router,
)

_STATIC_DIR = Path(__file__).parent / "static"


def setup_configs() -> Configs:
    return load_configs()


def setup_routes(app: FastAPI) -> None:
    app.include_router(root_router)
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(user_experiences_router)
    app.include_router(my_user_experiences_router)
    app.include_router(user_social_links_router)
    app.include_router(my_user_social_links_router)
    app.include_router(product_router)
    app.include_router(product_course_router)
    app.include_router(product_qa_router)
    app.include_router(product_ws_router)
    app.include_router(cohort_router)
    app.include_router(webinar_schedule_router)
    app.include_router(webinar_session_router)
    app.include_router(webinar_enrollment_router)
    app.include_router(my_webinar_enrollments_router)
    app.include_router(course_enrollment_router)
    app.include_router(my_course_enrollments_router)
    app.include_router(course_content_router)
    app.include_router(course_release_router)
    app.include_router(course_student_content_router)
    app.include_router(presence_router)
    app.include_router(product_roles_router)
    app.include_router(standalone_role_router)
    app.include_router(product_collaboration_router)
    app.include_router(collaboration_router)
    app.include_router(my_collaborations_router)
    app.include_router(notification_router)
    app.include_router(notification_ws_router)
    app.include_router(notification_preferences_router)
    app.include_router(push_public_router)
    app.include_router(push_me_router)
    app.include_router(auth_ws_router)
    app.mount(
        "/",
        StaticFiles(directory=_STATIC_DIR),
        name="static",
    )


def setup_map_tables() -> None:
    map_user_table()
    map_user_experience_table()
    map_user_social_link_table()
    map_file_table()
    map_product_table()
    map_webinar_details_table()
    map_product_qa_table()
    map_cohort_table()
    map_webinar_schedule_table()
    map_webinar_session_table()
    map_webinar_enrollment_table()
    map_course_enrollment_table()
    map_course_module_table()
    map_course_lesson_table()
    map_course_release_table()
    map_role_table()
    map_product_collaboration_table()
    map_collaboration_grant_table()
    map_notification_table()
    map_push_subscription_table()
