from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from learnic.infrastructure.configs import Configs, load_configs
from learnic.infrastructure.persistence.models.blog_post import (
    map_blog_post_table,
)
from learnic.infrastructure.persistence.models.enrollment import (
    map_enrollment_table,
)
from learnic.infrastructure.persistence.models.note_lesson import (
    map_note_lesson_table,
)
from learnic.infrastructure.persistence.models.note_module import (
    map_note_module_table,
)
from learnic.infrastructure.persistence.models.note_release import (
    map_note_release_table,
)
from learnic.infrastructure.persistence.models.file import map_file_table
from learnic.infrastructure.persistence.models.product import (
    map_product_qa_table,
    map_product_table,
)
from learnic.infrastructure.persistence.models.email_sending import (
    map_email_sending_table,
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
from learnic.infrastructure.persistence.models.product_gift import (
    map_product_gift_table,
)
from learnic.infrastructure.persistence.models.role import map_role_table
from learnic.infrastructure.persistence.models.statistic import (
    map_statistic_table,
)
from learnic.infrastructure.persistence.models.tag import map_tag_table
from learnic.infrastructure.persistence.models.subscription import (
    map_storage_quota_breach_table,
    map_subscription_table,
)
from learnic.infrastructure.persistence.models.user import map_user_table
from learnic.infrastructure.persistence.models.user_experience import (
    map_user_experience_table,
)
from learnic.infrastructure.persistence.models.user_social_link import (
    map_user_social_link_table,
)
from learnic.presentation.http.routes.admin import router as admin_router
from learnic.presentation.http.routes.auth import router as auth_router
from learnic.presentation.http.routes.blog_post import (
    admin_router as blog_admin_router,
    public_router as blog_public_router,
)
from learnic.presentation.http.routes.note_content import (
    router as note_content_router,
)
from learnic.presentation.http.routes.enrollment import (
    note_router as note_enrollment_router,
    me_router as my_enrollments_router,
)
from learnic.presentation.http.routes.note_release import (
    router as note_release_router,
    student_router as note_student_content_router,
)
from learnic.presentation.http.routes.presence import (
    router as presence_router,
)
from learnic.presentation.http.routes.product import (
    note_router as product_note_router,
    me_router as my_products_router,
    router as product_router,
)
from learnic.presentation.http.routes.product_collaboration import (
    collab_router as collaboration_router,
    me_router as my_collaborations_router,
    product_router as product_collaboration_router,
)
from learnic.presentation.http.routes.product_gift import (
    gift_router,
    product_router as product_gift_router,
)
from learnic.presentation.http.routes.notification import (
    router as notification_router,
)
from learnic.presentation.http.routes.notification_preferences import (
    router as notification_preferences_router,
)
from learnic.presentation.http.routes.subscription import (
    note_router as note_storage_router,
    router as subscription_router,
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
from learnic.presentation.http.routes.tag import (
    product_tags_router,
    tag_router,
)
from learnic.presentation.http.routes.product_cursors_ws import (
    router as product_cursors_ws_router,
)
from learnic.presentation.http.routes.product_ws import (
    router as product_ws_router,
)
from learnic.presentation.http.routes.root import router as root_router
from learnic.presentation.http.routes.user import router as user_router
from learnic.presentation.http.routes.user_experience import (
    me_router as my_user_experiences_router,
    router as user_experiences_router,
)
from learnic.presentation.http.routes.user_social_link import (
    me_router as my_user_social_links_router,
    router as user_social_links_router,
)
from learnic.presentation.http.routes.dev import dev_router

_STATIC_DIR = Path(__file__).parent / "static"


def setup_configs() -> Configs:
    return load_configs()


def setup_routes(app: FastAPI, configs: Configs) -> None:
    app.include_router(root_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(blog_public_router)
    app.include_router(blog_admin_router)
    app.include_router(user_router)
    app.include_router(user_experiences_router)
    app.include_router(my_user_experiences_router)
    app.include_router(user_social_links_router)
    app.include_router(my_user_social_links_router)
    app.include_router(product_router)
    app.include_router(product_note_router)
    app.include_router(my_products_router)
    app.include_router(product_qa_router)
    app.include_router(product_ws_router)
    app.include_router(product_cursors_ws_router)
    app.include_router(note_enrollment_router)
    app.include_router(my_enrollments_router)
    app.include_router(note_content_router)
    app.include_router(note_release_router)
    app.include_router(note_student_content_router)
    app.include_router(presence_router)
    app.include_router(product_roles_router)
    app.include_router(standalone_role_router)
    app.include_router(tag_router)
    app.include_router(product_tags_router)
    app.include_router(product_collaboration_router)
    app.include_router(collaboration_router)
    app.include_router(my_collaborations_router)
    app.include_router(product_gift_router)
    app.include_router(gift_router)
    app.include_router(notification_router)
    app.include_router(notification_ws_router)
    app.include_router(notification_preferences_router)
    app.include_router(push_public_router)
    app.include_router(push_me_router)
    app.include_router(subscription_router)
    app.include_router(note_storage_router)
    app.include_router(auth_ws_router)
    if configs.app.environment == "development":
        # Dev-only router — physically absent from prod builds.
        # See dev.py's module docstring for the safety rationale.
        app.include_router(dev_router)
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
    map_blog_post_table()
    map_product_table()
    map_product_qa_table()
    map_enrollment_table()
    map_note_module_table()
    map_note_lesson_table()
    map_note_release_table()
    map_role_table()
    map_tag_table()
    map_product_collaboration_table()
    map_collaboration_grant_table()
    map_product_gift_table()
    map_notification_table()
    map_push_subscription_table()
    map_statistic_table()
    map_subscription_table()
    map_storage_quota_breach_table()
    map_email_sending_table()
