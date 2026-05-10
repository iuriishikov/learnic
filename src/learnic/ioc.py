from collections.abc import AsyncIterator

import aioboto3
import httpx
from jinja2 import Environment
from dishka import (
    AsyncContainer,
    Provider,
    Scope,
    from_context,
    make_async_container,
    provide,
)
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from types_aiobotocore_s3 import S3Client

from learnic.application.commands.auth.login import LoginCommandHandler
from learnic.application.commands.auth.logout import LogoutCommandHandler
from learnic.application.commands.auth.logout_all import (
    LogoutAllCommandHandler,
)
from learnic.application.commands.auth.refresh import RefreshCommandHandler
from learnic.application.commands.auth.register import (
    RegisterCommandHandler,
)
from learnic.application.commands.auth.request_password_reset import (
    RequestPasswordResetCommandHandler,
)
from learnic.application.commands.auth.resend_verification import (
    ResendVerificationCommandHandler,
)
from learnic.application.commands.auth.reset_password import (
    ResetPasswordCommandHandler,
)
from learnic.application.commands.auth.verify_email import (
    VerifyEmailCommandHandler,
)
from learnic.application.commands.auth.verify_token import (
    VerifyTokenCommandHandler,
)
from learnic.application.commands.auth.verify_wait import (
    VerifyWaitCommandHandler,
)
from learnic.application.queries.auth.token_status import (
    GetTokenStatusQueryHandler,
)
from learnic.application.commands.cohort.add import (
    AddCohortCommandHandler,
)
from learnic.application.commands.course_block.add_code import (
    AddCodeBlockCommandHandler,
)
from learnic.application.commands.course_block.add_html import (
    AddHtmlBlockCommandHandler,
)
from learnic.application.commands.course_block.add_katex import (
    AddKatexBlockCommandHandler,
)
from learnic.application.commands.course_block.add_rutube_video import (
    AddRutubeVideoBlockCommandHandler,
)
from learnic.application.commands.course_block.delete import (
    DeleteLessonBlockCommandHandler,
)
from learnic.application.commands.course_block.reorder import (
    ReorderLessonBlocksCommandHandler,
)
from learnic.application.commands.course_block.update_code import (
    UpdateCodeBlockCommandHandler,
)
from learnic.application.commands.course_block.update_html import (
    UpdateHtmlBlockCommandHandler,
)
from learnic.application.commands.course_block.update_katex import (
    UpdateKatexBlockCommandHandler,
)
from learnic.application.commands.course_block.update_rutube_video import (
    UpdateRutubeVideoBlockCommandHandler,
)
from learnic.application.commands.course_draft.reset import (
    ResetCourseDraftCommandHandler,
)
from learnic.application.commands.course_enrollment.complete import (
    CompleteCourseEnrollmentCommandHandler,
)
from learnic.application.commands.course_lesson.add import (
    AddCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.delete import (
    DeleteCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.move import (
    MoveCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.rename import (
    RenameCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.reorder import (
    ReorderCourseLessonsCommandHandler,
)
from learnic.application.commands.course_module.add import (
    AddCourseModuleCommandHandler,
)
from learnic.application.commands.course_module.delete import (
    DeleteCourseModuleCommandHandler,
)
from learnic.application.commands.course_module.rename import (
    RenameCourseModuleCommandHandler,
)
from learnic.application.commands.course_module.reorder import (
    ReorderCourseModulesCommandHandler,
)
from learnic.application.commands.course_module.update_description import (
    UpdateCourseModuleDescriptionCommandHandler,
)
from learnic.application.commands.course_release.create import (
    CreateCourseReleaseCommandHandler,
)
from learnic.application.commands.course_enrollment.enroll import (
    EnrollStudentInCourseCommandHandler,
)
from learnic.application.commands.course_enrollment.refund import (
    RefundCourseEnrollmentCommandHandler,
)
from learnic.application.commands.course_enrollment.update_progress import (
    UpdateCourseProgressCommandHandler,
)
from learnic.application.commands.cohort.cancel import (
    CancelCohortCommandHandler,
)
from learnic.application.commands.cohort.close_enrollment import (
    CloseCohortEnrollmentCommandHandler,
)
from learnic.application.commands.cohort.complete import (
    CompleteCohortCommandHandler,
)
from learnic.application.commands.cohort.mark_full import (
    MarkCohortFullCommandHandler,
)
from learnic.application.commands.cohort.open_enrollment import (
    OpenCohortEnrollmentCommandHandler,
)
from learnic.application.commands.cohort.reschedule import (
    RescheduleCohortCommandHandler,
)
from learnic.application.commands.cohort.start import (
    StartCohortCommandHandler,
)
from learnic.application.commands.cohort.update_max_participants import (
    UpdateCohortMaxParticipantsCommandHandler,
)
from learnic.application.commands.cohort.update_name import (
    UpdateCohortNameCommandHandler,
)
from learnic.application.commands.product.add_course import (
    AddCourseProductCommandHandler,
)
from learnic.application.commands.product.add_webinar import (
    AddWebinarProductCommandHandler,
)
from learnic.application.commands.product.archive import (
    ArchiveProductCommandHandler,
)
from learnic.application.commands.product.change_description import (
    ChangeProductDescriptionCommandHandler,
)
from learnic.application.commands.product.change_duration import (
    ChangeProductDurationCommandHandler,
)
from learnic.application.commands.product.change_name import (
    ChangeProductNameCommandHandler,
)
from learnic.application.commands.product.cover.remove import (
    RemoveProductCoverCommandHandler,
)
from learnic.application.commands.product.cover.set import (
    SetProductCoverCommandHandler,
)
from learnic.application.commands.product.delete import (
    DeleteProductCommandHandler,
)
from learnic.application.commands.product.publish import (
    PublishProductCommandHandler,
)
from learnic.application.commands.product.unarchive import (
    UnarchiveProductCommandHandler,
)
from learnic.application.commands.product.update_webinar_defaults import (
    UpdateWebinarDefaultsCommandHandler,
)
from learnic.application.commands.product_collaboration.accept import (
    AcceptCollaborationInviteCommandHandler,
)
from learnic.application.commands.product_collaboration.accept_in_app import (
    AcceptCollaborationInAppCommandHandler,
)
from learnic.application.commands.product_collaboration.decline_in_app import (
    DeclineCollaborationInAppCommandHandler,
)
from learnic.application.commands.product_collaboration.invite_by_email import (
    InviteCollaboratorByEmailCommandHandler,
)
from learnic.application.commands.product_collaboration.invite_by_user import (
    InviteCollaboratorByUserCommandHandler,
)
from learnic.application.commands.product_collaboration.leave import (
    LeaveProductCommandHandler,
)
from learnic.application.commands.product_collaboration.reinvite import (
    ReinviteCollaboratorCommandHandler,
)
from learnic.application.commands.product_collaboration.revoke import (
    RevokeCollaborationCommandHandler,
)
from learnic.application.commands.product_collaboration.update_grants import (
    UpdateCollaborationGrantsCommandHandler,
)
from learnic.application.commands.notification.mark_all_as_read import (
    MarkAllNotificationsAsReadCommandHandler,
)
from learnic.application.commands.notification.mark_as_read import (
    MarkNotificationAsReadCommandHandler,
)
from learnic.application.commands.product_qa.add import (
    AddProductQACommandHandler,
)
from learnic.application.commands.role.create import (
    CreateCustomRoleCommandHandler,
)
from learnic.application.commands.role.delete import (
    DeleteCustomRoleCommandHandler,
)
from learnic.application.commands.role.update import (
    UpdateCustomRoleCommandHandler,
)
from learnic.application.commands.session.revoke import (
    RevokeSessionCommandHandler,
)
from learnic.application.queries.product_collaboration.get_my_permissions import (
    GetMyEffectivePermissionsQueryHandler,
)
from learnic.application.queries.product_collaboration.list_for_product import (
    ListProductCollaboratorsQueryHandler,
)
from learnic.application.queries.product_collaboration.list_my import (
    ListMyCollaborationsQueryHandler,
)
from learnic.application.queries.notification.get_counters import (
    GetMyNotificationCountersQueryHandler,
)
from learnic.application.queries.notification.list_my import (
    ListMyNotificationsQueryHandler,
)
from learnic.application.queries.role.get import GetRoleQueryHandler
from learnic.application.queries.role.list import (
    ListProductRolesQueryHandler,
)
from learnic.application.commands.product_qa.change_answer import (
    ChangeProductQAAnswerCommandHandler,
)
from learnic.application.commands.product_qa.change_question import (
    ChangeProductQAQuestionCommandHandler,
)
from learnic.application.commands.product_qa.delete import (
    DeleteProductQACommandHandler,
)
from learnic.application.commands.product_qa.reorder import (
    ReorderProductQACommandHandler,
)
from learnic.application.commands.user.avatar.remove import (
    RemoveUserAvatarCommandHandler,
)
from learnic.application.commands.webinar_enrollment.complete import (
    CompleteWebinarEnrollmentCommandHandler,
)
from learnic.application.commands.webinar_enrollment.drop import (
    DropWebinarEnrollmentCommandHandler,
)
from learnic.application.commands.webinar_enrollment.enroll import (
    EnrollStudentInCohortCommandHandler,
)
from learnic.application.commands.webinar_enrollment.refund import (
    RefundWebinarEnrollmentCommandHandler,
)
from learnic.application.commands.webinar_schedule.add import (
    AddWebinarScheduleCommandHandler,
)
from learnic.application.commands.webinar_schedule.delete import (
    DeleteWebinarScheduleCommandHandler,
)
from learnic.application.commands.webinar_schedule.materialize import (
    MaterializeWebinarScheduleCommandHandler,
)
from learnic.application.commands.webinar_schedule.update import (
    UpdateWebinarScheduleCommandHandler,
)
from learnic.application.commands.webinar_session.add_one_off import (
    AddOneOffWebinarSessionCommandHandler,
)
from learnic.application.commands.webinar_session.attach_recording import (
    AttachWebinarSessionRecordingCommandHandler,
)
from learnic.application.commands.webinar_session.cancel import (
    CancelWebinarSessionCommandHandler,
)
from learnic.application.commands.webinar_session.change_stream_url import (
    ChangeWebinarSessionStreamUrlCommandHandler,
)
from learnic.application.commands.webinar_session.complete import (
    CompleteWebinarSessionCommandHandler,
)
from learnic.application.commands.webinar_session.remove_recording import (
    RemoveWebinarSessionRecordingCommandHandler,
)
from learnic.application.commands.webinar_session.reschedule import (
    RescheduleWebinarSessionCommandHandler,
)
from learnic.application.commands.user.avatar.set import (
    SetUserAvatarCommandHandler,
)
from learnic.application.commands.user.change_description import (
    ChangeUserDescriptionCommandHandler,
)
from learnic.application.commands.user.change_first_name import (
    ChangeUserFirstNameCommandHandler,
)
from learnic.application.commands.user.change_last_name import (
    ChangeUserLastNameCommandHandler,
)
from learnic.application.commands.user.change_patronymic import (
    ChangeUserPatronymicCommandHandler,
)
from learnic.application.commands.user.cover.remove import (
    RemoveUserCoverCommandHandler,
)
from learnic.application.commands.user.cover.set import (
    SetUserCoverCommandHandler,
)
from learnic.application.common.email.sender import EmailSender
from learnic.application.common.email.service import EmailService
from learnic.application.common.persistence.cohort import (
    CohortGateway,
    CohortReader,
)
from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.course_content import (
    CourseContentReader,
)
from learnic.application.common.persistence.course_draft import (
    CourseDraftResetter,
)
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentGateway,
    CourseEnrollmentReader,
)
from learnic.application.common.persistence.course_lesson import (
    CourseLessonGateway,
)
from learnic.application.common.persistence.course_module import (
    CourseModuleGateway,
)
from learnic.application.common.persistence.course_release import (
    CourseReleaseGateway,
    CourseReleaseReader,
    CourseReleaseSnapshotter,
)
from learnic.application.common.persistence.file import (
    FilesGateway,
    FilesReader,
)
from learnic.application.common.persistence.product import (
    ProductGateway,
    ProductReader,
)
from learnic.application.common.persistence.product_qa import (
    ProductQAGateway,
    ProductQAReader,
)
from learnic.application.common.notifications.event_bus import (
    NotificationEventBus,
)
from learnic.application.common.notifications.gateway import (
    NotificationGateway,
)
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.notifications.reader import (
    NotificationReader,
)
from learnic.application.common.notification_preferences.gateway import (
    NotificationPreferencesGateway,
)
from learnic.application.common.notification_preferences.reader import (
    NotificationPreferencesReader,
    NotificationPreferencesReaderService,
)
from learnic.application.common.push.gateway import PushSubscriptionGateway
from learnic.application.common.push.sender import PushSender
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
    ProductCollaborationReader,
    ProductCollaborationSaver,
)
from learnic.application.common.persistence.role import (
    RoleGateway,
    RoleReader,
    RoleSaver,
)
from learnic.application.common.persistence.session import SessionsReader
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.auth.confirm_events import ConfirmEventBus
from learnic.application.common.auth.resource_lineage import (
    ResourceLineageReader,
)
from learnic.application.common.auth.role_hierarchy import (
    ProductOwnerResolver,
    RoleHierarchy,
    RoleHierarchyService,
)
from learnic.application.common.persistence.webinar_enrollment import (
    WebinarEnrollmentGateway,
    WebinarEnrollmentReader,
)
from learnic.application.common.persistence.webinar_schedule import (
    WebinarScheduleGateway,
    WebinarScheduleReader,
)
from learnic.application.common.persistence.webinar_session import (
    WebinarSessionGateway,
    WebinarSessionReader,
)
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.user import (
    UserGateway,
    UserReader,
)
from learnic.application.common.collaboration.event_bus import (
    ContentEventBus,
)
from learnic.application.common.presence.event_bus import PresenceEventBus
from learnic.application.common.product_events.event_bus import (
    ProductEventBus,
)
from learnic.application.common.presence.tracker import PresenceTracker
from learnic.application.common.scheduling.materializer import (
    ScheduleMaterializer,
)
from learnic.application.common.scheduling.recurrence import (
    RecurrenceRuleValidator,
)
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.email_tokens import EmailTokenStore
from learnic.application.common.security.html import HtmlSanitizer
from learnic.application.common.security.passwords import PasswordHasher
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.application.queries.presence.get_user_presence import (
    GetUserPresenceQueryHandler,
)
from learnic.application.queries.presence.get_users_presence import (
    GetUsersPresenceQueryHandler,
)
from learnic.application.queries.session.list_my import (
    ListMySessionsQueryHandler,
)
from learnic.application.queries.user.get import GetUserQueryHandler
from learnic.application.queries.user.get_avatar import (
    GetUserAvatarQueryHandler,
)
from learnic.application.queries.user.search import (
    SearchUsersQueryHandler,
)
from learnic.application.queries.product.check_name_availability import (
    CheckProductNameAvailabilityQueryHandler,
)
from learnic.application.queries.product.get import (
    GetProductQueryHandler,
)
from learnic.application.queries.product.get_my import (
    GetMyProductsQueryHandler,
)
from learnic.application.queries.product.get_published import (
    GetPublishedProductsQueryHandler,
)
from learnic.application.queries.cohort.get import (
    GetCohortQueryHandler,
)
from learnic.application.queries.cohort.get_for_webinar import (
    GetWebinarCohortsQueryHandler,
)
from learnic.application.queries.course_content.get_draft import (
    GetCourseDraftQueryHandler,
)
from learnic.application.queries.course_content.get_for_student import (
    GetMyCourseContentQueryHandler,
)
from learnic.application.queries.course_release.get_content import (
    GetCourseReleaseContentQueryHandler,
)
from learnic.application.queries.course_release.list_for_product import (
    ListCourseReleasesQueryHandler,
)
from learnic.application.queries.course_enrollment.list_for_product import (
    GetProductCourseEnrollmentsQueryHandler,
)
from learnic.application.queries.course_enrollment.list_for_student import (
    GetStudentCourseEnrollmentsQueryHandler,
)
from learnic.application.queries.product_qa.list import (
    GetProductQAListQueryHandler,
)
from learnic.application.queries.user.get_cover import (
    GetUserCoverQueryHandler,
)
from learnic.application.queries.webinar_enrollment.list_for_cohort import (
    GetCohortEnrollmentsQueryHandler,
)
from learnic.application.queries.webinar_enrollment.list_for_student import (
    GetStudentWebinarEnrollmentsQueryHandler,
)
from learnic.application.queries.webinar_schedule.list_for_cohort import (
    GetCohortSchedulesQueryHandler,
)
from learnic.application.queries.webinar_session.get import (
    GetWebinarSessionQueryHandler,
)
from learnic.application.queries.webinar_session.list_for_cohort import (
    GetCohortSessionsQueryHandler,
)
from learnic.application.commands.notification_preferences.update import (
    UpdateNotificationPreferencesCommandHandler,
)
from learnic.application.commands.push.send_to_user import (
    SendPushToUserCommandHandler,
)
from learnic.application.commands.push.subscribe import (
    SubscribePushCommandHandler,
)
from learnic.application.commands.push.unsubscribe import (
    UnsubscribePushCommandHandler,
)
from learnic.application.queries.notification_preferences.get_my import (
    GetMyNotificationPreferencesQueryHandler,
)
from learnic.application.queries.push.list_my import (
    ListMyPushSubscriptionsQueryHandler,
)
from learnic.infrastructure.configs import (
    ASGIConfig,
    Configs,
    PostgresConfig,
    RedisConfig,
    RusenderConfig,
    S3Config,
    SecurityConfig,
    TaskIQConfig,
    WebPushConfig,
)
from learnic.infrastructure.email.adapters.rusender import (
    RusenderEmailSender,
)
from learnic.infrastructure.email.renderer import (
    EmailRenderer,
    build_environment,
)
from learnic.infrastructure.email.service import TemplatedEmailService
from learnic.infrastructure.persistence.adapters.email_token import (
    EmailTokenStoreAlchemy,
)
from learnic.infrastructure.persistence.adapters.cohort import (
    CohortMapperAlchemy,
    CohortReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_block import (
    LessonBlockGatewayAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_content import (
    CourseContentReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_draft import (
    CourseDraftResetterAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_enrollment import (
    CourseEnrollmentMapperAlchemy,
    CourseEnrollmentReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_lesson import (
    CourseLessonMapperAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_module import (
    CourseModuleMapperAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_release import (
    CourseReleaseMapperAlchemy,
    CourseReleaseReaderAlchemy,
    CourseReleaseSnapshotterAlchemy,
)
from learnic.infrastructure.persistence.adapters.file import (
    FilesMapperAlchemy,
    FilesReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.product import (
    ProductMapperAlchemy,
    ProductReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.product_qa import (
    ProductQAMapperAlchemy,
    ProductQAReaderAlchemy,
)
from learnic.infrastructure.notifications.event_bus_redis import (
    NotificationEventBusRedis,
)
from learnic.infrastructure.persistence.adapters.notification import (
    NotificationGatewayAlchemy,
    NotificationReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.notification_preferences import (
    NotificationPreferencesMapperAlchemy,
)
from learnic.infrastructure.persistence.adapters.push_subscription import (
    PushSubscriptionGatewayAlchemy,
)
from learnic.infrastructure.push.sender_pywebpush import PywebpushSender
from learnic.infrastructure.persistence.adapters.product_collaboration import (
    ProductCollaborationMapperAlchemy,
    ProductCollaborationReaderAlchemy,
    ProductCollaborationSaverAlchemy,
)
from learnic.infrastructure.persistence.adapters.resource_lineage import (
    ResourceLineageReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.role import (
    RoleMapperAlchemy,
    RoleReaderAlchemy,
    RoleSaverAlchemy,
)
from learnic.infrastructure.auth.authorizer import AuthorizerService
from learnic.infrastructure.auth.confirm_events_redis import (
    ConfirmEventBusRedis,
)
from learnic.infrastructure.auth.product_owner_resolver import (
    ProductOwnerResolverAlchemy,
)
from learnic.infrastructure.persistence.adapters.webinar_enrollment import (
    WebinarEnrollmentMapperAlchemy,
    WebinarEnrollmentReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.webinar_schedule import (
    WebinarScheduleMapperAlchemy,
    WebinarScheduleReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.webinar_session import (
    WebinarSessionMapperAlchemy,
    WebinarSessionReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.refresh_token import (
    RefreshTokenStoreAlchemy,
)
from learnic.infrastructure.persistence.adapters.session import (
    SessionsReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.signup_session import (
    SignupSessionStoreAlchemy,
)
from learnic.infrastructure.persistence.adapters.token_denylist import (
    TokenDenylistAlchemy,
)
from learnic.infrastructure.persistence.adapters.transaction import (
    EntitySaverAlchemy,
    TransactionAlchemy,
)
from learnic.infrastructure.persistence.adapters.user import (
    UserMapperAlchemy,
    UserReaderAlchemy,
)
from learnic.infrastructure.collaboration.event_bus_redis import (
    ContentEventBusRedis,
)
from learnic.infrastructure.presence.adapters.event_bus_redis import (
    PresenceEventBusRedis,
)
from learnic.infrastructure.product_events.event_bus_redis import (
    ProductEventBusRedis,
)
from learnic.infrastructure.presence.adapters.tracker_redis import (
    PresenceTrackerRedis,
)
from learnic.infrastructure.scheduling.dateutil_materializer import (
    DateutilScheduleMaterializer,
)
from learnic.infrastructure.scheduling.dateutil_recurrence import (
    DateutilRecurrenceRuleValidator,
)
from learnic.infrastructure.security.argon2_hasher import (
    Argon2PasswordHasher,
)
from learnic.infrastructure.security.bleach_html_sanitizer import (
    BleachHtmlSanitizer,
)
from learnic.infrastructure.security.jwt_access import JwtAccessTokenService
from learnic.infrastructure.storage.adapters.s3 import S3FileStorage
from learnic.infrastructure.tasks.scheduler import TaskSchedulerTaskIQ
from learnic.presentation.http.common.auth_deps import Authenticator


class ConfigsProvider(Provider):
    scope = Scope.APP

    configs = from_context(provides=Configs, scope=Scope.APP)

    @provide
    def postgres_config(self, configs: Configs) -> PostgresConfig:
        return configs.postgres

    @provide
    def asgi_config(self, configs: Configs) -> ASGIConfig:
        return configs.asgi

    @provide
    def s3_config(self, configs: Configs) -> S3Config:
        return configs.s3

    @provide
    def taskiq_config(self, configs: Configs) -> TaskIQConfig:
        return configs.taskiq

    @provide
    def redis_config(self, configs: Configs) -> RedisConfig:
        return configs.redis

    @provide
    def rusender_config(self, configs: Configs) -> RusenderConfig:
        return configs.rusender

    @provide
    def security_config(self, configs: Configs) -> SecurityConfig:
        return configs.security

    @provide
    def web_push_config(self, configs: Configs) -> WebPushConfig:
        return configs.web_push


class DBProvider(Provider):
    scope = Scope.APP

    @provide
    async def engine(
        self,
        postgres: PostgresConfig,
    ) -> AsyncIterator[AsyncEngine]:
        engine = create_async_engine(postgres.dsn_async, echo=postgres.debug)
        try:
            yield engine
        finally:
            await engine.dispose()

    @provide
    def session_maker(
        self,
        engine: AsyncEngine,
    ) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        maker: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session


class GatewaysProvider(Provider):
    scope = Scope.REQUEST

    transaction = provide(TransactionAlchemy, provides=Transaction)
    entity_saver = provide(EntitySaverAlchemy, provides=EntitySaver)
    user_gateway = provide(UserMapperAlchemy, provides=UserGateway)
    user_reader = provide(UserReaderAlchemy, provides=UserReader)
    files_gateway = provide(FilesMapperAlchemy, provides=FilesGateway)
    files_reader = provide(FilesReaderAlchemy, provides=FilesReader)
    product_gateway = provide(
        ProductMapperAlchemy,
        provides=ProductGateway,
    )
    product_reader = provide(
        ProductReaderAlchemy,
        provides=ProductReader,
    )
    product_qa_gateway = provide(
        ProductQAMapperAlchemy,
        provides=ProductQAGateway,
    )
    product_qa_reader = provide(
        ProductQAReaderAlchemy,
        provides=ProductQAReader,
    )
    cohort_gateway = provide(
        CohortMapperAlchemy,
        provides=CohortGateway,
    )
    cohort_reader = provide(
        CohortReaderAlchemy,
        provides=CohortReader,
    )
    webinar_schedule_gateway = provide(
        WebinarScheduleMapperAlchemy,
        provides=WebinarScheduleGateway,
    )
    webinar_schedule_reader = provide(
        WebinarScheduleReaderAlchemy,
        provides=WebinarScheduleReader,
    )
    webinar_session_gateway = provide(
        WebinarSessionMapperAlchemy,
        provides=WebinarSessionGateway,
    )
    webinar_session_reader = provide(
        WebinarSessionReaderAlchemy,
        provides=WebinarSessionReader,
    )
    webinar_enrollment_gateway = provide(
        WebinarEnrollmentMapperAlchemy,
        provides=WebinarEnrollmentGateway,
    )
    webinar_enrollment_reader = provide(
        WebinarEnrollmentReaderAlchemy,
        provides=WebinarEnrollmentReader,
    )
    course_enrollment_gateway = provide(
        CourseEnrollmentMapperAlchemy,
        provides=CourseEnrollmentGateway,
    )
    course_enrollment_reader = provide(
        CourseEnrollmentReaderAlchemy,
        provides=CourseEnrollmentReader,
    )
    course_module_gateway = provide(
        CourseModuleMapperAlchemy,
        provides=CourseModuleGateway,
    )
    course_lesson_gateway = provide(
        CourseLessonMapperAlchemy,
        provides=CourseLessonGateway,
    )
    course_content_reader = provide(
        CourseContentReaderAlchemy,
        provides=CourseContentReader,
    )
    lesson_block_gateway = provide(
        LessonBlockGatewayAlchemy,
        provides=LessonBlockGateway,
    )
    course_release_gateway = provide(
        CourseReleaseMapperAlchemy,
        provides=CourseReleaseGateway,
    )
    course_release_snapshotter = provide(
        CourseReleaseSnapshotterAlchemy,
        provides=CourseReleaseSnapshotter,
    )
    course_release_reader = provide(
        CourseReleaseReaderAlchemy,
        provides=CourseReleaseReader,
    )
    course_draft_resetter = provide(
        CourseDraftResetterAlchemy,
        provides=CourseDraftResetter,
    )
    role_gateway = provide(
        RoleMapperAlchemy,
        provides=RoleGateway,
    )
    role_reader = provide(
        RoleReaderAlchemy,
        provides=RoleReader,
    )
    role_saver = provide(
        RoleSaverAlchemy,
        provides=RoleSaver,
    )
    product_collaboration_gateway = provide(
        ProductCollaborationMapperAlchemy,
        provides=ProductCollaborationGateway,
    )
    product_collaboration_reader = provide(
        ProductCollaborationReaderAlchemy,
        provides=ProductCollaborationReader,
    )
    product_collaboration_saver = provide(
        ProductCollaborationSaverAlchemy,
        provides=ProductCollaborationSaver,
    )
    notification_gateway = provide(
        NotificationGatewayAlchemy,
        provides=NotificationGateway,
    )
    notification_reader = provide(
        NotificationReaderAlchemy,
        provides=NotificationReader,
    )
    notification_publisher = provide(NotificationPublisher)
    notification_preferences_gateway = provide(
        NotificationPreferencesMapperAlchemy,
        provides=NotificationPreferencesGateway,
    )
    notification_preferences_reader = provide(
        NotificationPreferencesReaderService,
        provides=NotificationPreferencesReader,
    )
    push_subscription_gateway = provide(
        PushSubscriptionGatewayAlchemy,
        provides=PushSubscriptionGateway,
    )
    resource_lineage_reader = provide(
        ResourceLineageReaderAlchemy,
        provides=ResourceLineageReader,
    )
    sessions_reader = provide(
        SessionsReaderAlchemy,
        provides=SessionsReader,
    )
    authorizer = provide(
        AuthorizerService,
        provides=Authorizer,
    )
    product_owner_resolver = provide(
        ProductOwnerResolverAlchemy,
        provides=ProductOwnerResolver,
    )
    role_hierarchy = provide(
        RoleHierarchyService,
        provides=RoleHierarchy,
    )


class SecurityProvider(Provider):
    hasher = provide(Argon2PasswordHasher, provides=PasswordHasher, scope=Scope.APP)
    access_tokens = provide(
        JwtAccessTokenService,
        provides=AccessTokenService,
        scope=Scope.APP,
    )
    refresh_store = provide(
        RefreshTokenStoreAlchemy,
        provides=RefreshTokenStore,
        scope=Scope.REQUEST,
    )
    email_tokens = provide(
        EmailTokenStoreAlchemy,
        provides=EmailTokenStore,
        scope=Scope.REQUEST,
    )
    signup_sessions = provide(
        SignupSessionStoreAlchemy,
        provides=SignupSessionStore,
        scope=Scope.REQUEST,
    )
    denylist = provide(
        TokenDenylistAlchemy,
        provides=TokenDenylist,
        scope=Scope.REQUEST,
    )
    html_sanitizer = provide(
        BleachHtmlSanitizer,
        provides=HtmlSanitizer,
        scope=Scope.APP,
    )
    authenticator = provide(Authenticator, scope=Scope.REQUEST)


class S3Provider(Provider):
    scope = Scope.APP

    @provide
    def session(self) -> aioboto3.Session:
        return aioboto3.Session()

    @provide
    async def client(
        self,
        session: aioboto3.Session,
        s3: S3Config,
    ) -> AsyncIterator[S3Client]:
        async with session.client(
            "s3",
            endpoint_url=s3.endpoint,
            aws_access_key_id=s3.access_key,
            aws_secret_access_key=s3.secret_key,
            region_name=s3.region,
        ) as client:
            yield client

    @provide(scope=Scope.REQUEST)
    def file_storage(
        self,
        client: S3Client,
    ) -> FileStorage:
        return S3FileStorage(client)


class TasksProvider(Provider):
    scope = Scope.REQUEST

    scheduler = provide(TaskSchedulerTaskIQ, provides=TaskScheduler)


class PushProvider(Provider):
    scope = Scope.APP

    sender = provide(PywebpushSender, provides=PushSender)


class SchedulingProvider(Provider):
    scope = Scope.APP

    rule_validator = provide(
        DateutilRecurrenceRuleValidator,
        provides=RecurrenceRuleValidator,
    )
    materializer = provide(
        DateutilScheduleMaterializer,
        provides=ScheduleMaterializer,
    )


class RedisProvider(Provider):
    scope = Scope.APP

    @provide
    async def redis(
        self,
        config: RedisConfig,
    ) -> AsyncIterator[Redis]:
        client = Redis.from_url(config.url, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()


class PresenceProvider(Provider):
    scope = Scope.APP

    event_bus = provide(PresenceEventBusRedis, provides=PresenceEventBus)
    tracker = provide(PresenceTrackerRedis, provides=PresenceTracker)


class CollaborationProvider(Provider):
    scope = Scope.APP

    event_bus = provide(ContentEventBusRedis, provides=ContentEventBus)


class ProductEventsProvider(Provider):
    scope = Scope.APP

    event_bus = provide(ProductEventBusRedis, provides=ProductEventBus)


class NotificationEventsProvider(Provider):
    scope = Scope.APP

    event_bus = provide(
        NotificationEventBusRedis,
        provides=NotificationEventBus,
    )


class ConfirmEventsProvider(Provider):
    scope = Scope.APP

    event_bus = provide(ConfirmEventBusRedis, provides=ConfirmEventBus)


class InteractorsProvider(Provider):
    scope = Scope.REQUEST

    get_user = provide(GetUserQueryHandler)
    get_user_avatar = provide(GetUserAvatarQueryHandler)
    get_user_cover = provide(GetUserCoverQueryHandler)
    search_users = provide(SearchUsersQueryHandler)

    get_user_presence = provide(GetUserPresenceQueryHandler)
    get_users_presence = provide(GetUsersPresenceQueryHandler)

    register = provide(RegisterCommandHandler)
    login = provide(LoginCommandHandler)
    refresh = provide(RefreshCommandHandler)
    logout = provide(LogoutCommandHandler)
    logout_all = provide(LogoutAllCommandHandler)
    verify_email = provide(VerifyEmailCommandHandler)
    verify_wait = provide(VerifyWaitCommandHandler)
    verify_token = provide(VerifyTokenCommandHandler)
    resend_verification = provide(ResendVerificationCommandHandler)
    get_token_status = provide(GetTokenStatusQueryHandler)
    request_password_reset = provide(RequestPasswordResetCommandHandler)
    reset_password = provide(ResetPasswordCommandHandler)

    list_my_sessions = provide(ListMySessionsQueryHandler)
    revoke_session = provide(RevokeSessionCommandHandler)

    set_user_avatar = provide(SetUserAvatarCommandHandler)
    remove_user_avatar = provide(RemoveUserAvatarCommandHandler)
    set_user_cover = provide(SetUserCoverCommandHandler)
    remove_user_cover = provide(RemoveUserCoverCommandHandler)

    change_user_first_name = provide(ChangeUserFirstNameCommandHandler)
    change_user_last_name = provide(ChangeUserLastNameCommandHandler)
    change_user_patronymic = provide(ChangeUserPatronymicCommandHandler)
    change_user_description = provide(ChangeUserDescriptionCommandHandler)

    add_course_product = provide(AddCourseProductCommandHandler)
    add_webinar_product = provide(AddWebinarProductCommandHandler)
    change_product_name = provide(ChangeProductNameCommandHandler)
    change_product_description = provide(
        ChangeProductDescriptionCommandHandler,
    )
    change_product_duration = provide(ChangeProductDurationCommandHandler)
    set_product_cover = provide(SetProductCoverCommandHandler)
    remove_product_cover = provide(RemoveProductCoverCommandHandler)
    publish_product = provide(PublishProductCommandHandler)
    archive_product = provide(ArchiveProductCommandHandler)
    unarchive_product = provide(UnarchiveProductCommandHandler)
    delete_product = provide(DeleteProductCommandHandler)
    update_webinar_defaults = provide(UpdateWebinarDefaultsCommandHandler)
    get_product = provide(GetProductQueryHandler)
    get_my_products = provide(GetMyProductsQueryHandler)
    get_published_products = provide(GetPublishedProductsQueryHandler)
    check_product_name_availability = provide(
        CheckProductNameAvailabilityQueryHandler,
    )

    add_product_qa = provide(AddProductQACommandHandler)
    change_product_qa_question = provide(
        ChangeProductQAQuestionCommandHandler,
    )
    change_product_qa_answer = provide(ChangeProductQAAnswerCommandHandler)
    reorder_product_qa = provide(ReorderProductQACommandHandler)
    delete_product_qa = provide(DeleteProductQACommandHandler)
    get_product_qa_list = provide(GetProductQAListQueryHandler)

    add_cohort = provide(AddCohortCommandHandler)
    update_cohort_name = provide(UpdateCohortNameCommandHandler)
    update_cohort_max_participants = provide(
        UpdateCohortMaxParticipantsCommandHandler,
    )
    reschedule_cohort = provide(RescheduleCohortCommandHandler)
    open_cohort_enrollment = provide(OpenCohortEnrollmentCommandHandler)
    close_cohort_enrollment = provide(
        CloseCohortEnrollmentCommandHandler,
    )
    mark_cohort_full = provide(MarkCohortFullCommandHandler)
    start_cohort = provide(StartCohortCommandHandler)
    complete_cohort = provide(CompleteCohortCommandHandler)
    cancel_cohort = provide(CancelCohortCommandHandler)
    get_cohort = provide(GetCohortQueryHandler)
    get_webinar_cohorts = provide(GetWebinarCohortsQueryHandler)

    add_webinar_schedule = provide(AddWebinarScheduleCommandHandler)
    update_webinar_schedule = provide(
        UpdateWebinarScheduleCommandHandler,
    )
    delete_webinar_schedule = provide(
        DeleteWebinarScheduleCommandHandler,
    )
    materialize_webinar_schedule = provide(
        MaterializeWebinarScheduleCommandHandler,
    )
    get_cohort_schedules = provide(GetCohortSchedulesQueryHandler)

    add_one_off_webinar_session = provide(
        AddOneOffWebinarSessionCommandHandler,
    )
    reschedule_webinar_session = provide(
        RescheduleWebinarSessionCommandHandler,
    )
    cancel_webinar_session = provide(CancelWebinarSessionCommandHandler)
    complete_webinar_session = provide(
        CompleteWebinarSessionCommandHandler,
    )
    attach_webinar_session_recording = provide(
        AttachWebinarSessionRecordingCommandHandler,
    )
    remove_webinar_session_recording = provide(
        RemoveWebinarSessionRecordingCommandHandler,
    )
    change_webinar_session_stream_url = provide(
        ChangeWebinarSessionStreamUrlCommandHandler,
    )
    get_webinar_session = provide(GetWebinarSessionQueryHandler)
    get_cohort_sessions = provide(GetCohortSessionsQueryHandler)

    enroll_student_in_cohort = provide(
        EnrollStudentInCohortCommandHandler,
    )
    drop_webinar_enrollment = provide(
        DropWebinarEnrollmentCommandHandler,
    )
    complete_webinar_enrollment = provide(
        CompleteWebinarEnrollmentCommandHandler,
    )
    refund_webinar_enrollment = provide(
        RefundWebinarEnrollmentCommandHandler,
    )
    get_cohort_enrollments = provide(GetCohortEnrollmentsQueryHandler)
    get_student_webinar_enrollments = provide(
        GetStudentWebinarEnrollmentsQueryHandler,
    )

    enroll_student_in_course = provide(
        EnrollStudentInCourseCommandHandler,
    )
    update_course_progress = provide(
        UpdateCourseProgressCommandHandler,
    )
    complete_course_enrollment = provide(
        CompleteCourseEnrollmentCommandHandler,
    )
    refund_course_enrollment = provide(
        RefundCourseEnrollmentCommandHandler,
    )
    get_product_course_enrollments = provide(
        GetProductCourseEnrollmentsQueryHandler,
    )
    get_student_course_enrollments = provide(
        GetStudentCourseEnrollmentsQueryHandler,
    )

    add_course_module = provide(AddCourseModuleCommandHandler)
    rename_course_module = provide(RenameCourseModuleCommandHandler)
    update_course_module_description = provide(
        UpdateCourseModuleDescriptionCommandHandler,
    )
    reorder_course_modules = provide(ReorderCourseModulesCommandHandler)
    delete_course_module = provide(DeleteCourseModuleCommandHandler)
    add_course_lesson = provide(AddCourseLessonCommandHandler)
    rename_course_lesson = provide(RenameCourseLessonCommandHandler)
    move_course_lesson = provide(MoveCourseLessonCommandHandler)
    reorder_course_lessons = provide(ReorderCourseLessonsCommandHandler)
    delete_course_lesson = provide(DeleteCourseLessonCommandHandler)
    add_html_block = provide(AddHtmlBlockCommandHandler)
    add_katex_block = provide(AddKatexBlockCommandHandler)
    add_rutube_video_block = provide(AddRutubeVideoBlockCommandHandler)
    add_code_block = provide(AddCodeBlockCommandHandler)
    update_html_block = provide(UpdateHtmlBlockCommandHandler)
    update_katex_block = provide(UpdateKatexBlockCommandHandler)
    update_rutube_video_block = provide(UpdateRutubeVideoBlockCommandHandler)
    update_code_block = provide(UpdateCodeBlockCommandHandler)
    reorder_lesson_blocks = provide(ReorderLessonBlocksCommandHandler)
    delete_lesson_block = provide(DeleteLessonBlockCommandHandler)
    get_course_draft = provide(GetCourseDraftQueryHandler)
    get_my_course_content = provide(GetMyCourseContentQueryHandler)
    create_course_release = provide(CreateCourseReleaseCommandHandler)
    list_course_releases = provide(ListCourseReleasesQueryHandler)
    get_course_release_content = provide(
        GetCourseReleaseContentQueryHandler,
    )
    reset_course_draft = provide(ResetCourseDraftCommandHandler)

    create_custom_role = provide(CreateCustomRoleCommandHandler)
    update_custom_role = provide(UpdateCustomRoleCommandHandler)
    delete_custom_role = provide(DeleteCustomRoleCommandHandler)
    list_product_roles = provide(ListProductRolesQueryHandler)
    get_role = provide(GetRoleQueryHandler)

    invite_collaborator_by_user = provide(
        InviteCollaboratorByUserCommandHandler,
    )
    invite_collaborator_by_email = provide(
        InviteCollaboratorByEmailCommandHandler,
    )
    accept_collaboration_invite = provide(
        AcceptCollaborationInviteCommandHandler,
    )
    accept_collaboration_in_app = provide(
        AcceptCollaborationInAppCommandHandler,
    )
    decline_collaboration_in_app = provide(
        DeclineCollaborationInAppCommandHandler,
    )
    update_collaboration_grants = provide(
        UpdateCollaborationGrantsCommandHandler,
    )
    revoke_collaboration = provide(RevokeCollaborationCommandHandler)
    reinvite_collaborator = provide(ReinviteCollaboratorCommandHandler)
    leave_product = provide(LeaveProductCommandHandler)
    list_product_collaborators = provide(
        ListProductCollaboratorsQueryHandler,
    )
    list_my_collaborations = provide(ListMyCollaborationsQueryHandler)
    get_my_effective_permissions = provide(
        GetMyEffectivePermissionsQueryHandler,
    )

    list_my_notifications = provide(ListMyNotificationsQueryHandler)
    get_my_notification_counters = provide(
        GetMyNotificationCountersQueryHandler,
    )
    mark_notification_read = provide(MarkNotificationAsReadCommandHandler)
    mark_all_notifications_read = provide(
        MarkAllNotificationsAsReadCommandHandler,
    )

    subscribe_push = provide(SubscribePushCommandHandler)
    unsubscribe_push = provide(UnsubscribePushCommandHandler)
    list_my_push_subscriptions = provide(ListMyPushSubscriptionsQueryHandler)
    send_push_to_user = provide(SendPushToUserCommandHandler)
    get_my_notification_preferences = provide(
        GetMyNotificationPreferencesQueryHandler,
    )
    update_notification_preferences = provide(
        UpdateNotificationPreferencesCommandHandler,
    )


class EmailProvider(Provider):
    scope = Scope.APP

    @provide
    async def http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        client = httpx.AsyncClient(timeout=10.0)
        try:
            yield client
        finally:
            await client.aclose()

    @provide
    def jinja_environment(self) -> Environment:
        return build_environment()

    @provide
    def email_renderer(self, env: Environment) -> EmailRenderer:
        return EmailRenderer(env=env)

    @provide(scope=Scope.REQUEST)
    def email_sender(
        self,
        client: httpx.AsyncClient,
        rusender: RusenderConfig,
    ) -> EmailSender:
        return RusenderEmailSender(
            client=client,
            api_key=rusender.api_key,
            from_email=rusender.from_email,
            from_name=rusender.from_name,
        )

    @provide(scope=Scope.REQUEST)
    def email_service(
        self,
        renderer: EmailRenderer,
        sender: EmailSender,
    ) -> EmailService:
        return TemplatedEmailService(renderer=renderer, sender=sender)


def setup_providers(configs: Configs) -> AsyncContainer:
    return make_async_container(
        ConfigsProvider(),
        DBProvider(),
        GatewaysProvider(),
        SecurityProvider(),
        S3Provider(),
        TasksProvider(),
        PushProvider(),
        SchedulingProvider(),
        RedisProvider(),
        PresenceProvider(),
        CollaborationProvider(),
        ProductEventsProvider(),
        NotificationEventsProvider(),
        ConfirmEventsProvider(),
        EmailProvider(),
        InteractorsProvider(),
        context={Configs: configs},
    )
