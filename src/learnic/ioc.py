from collections.abc import AsyncIterator, Mapping

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
from learnic.application.commands.course_block.add_code import (
    AddCodeBlockCommandHandler,
)
from learnic.application.commands.course_block.check_answer import (
    CheckBlockAnswerCommandHandler,
)
from learnic.application.commands.course_block.reveal_answer import (
    RevealBlockAnswerCommandHandler,
)
from learnic.application.commands.course_block.add_html import (
    AddHtmlBlockCommandHandler,
)
from learnic.application.commands.course_block.add_katex import (
    AddKatexBlockCommandHandler,
)
from learnic.application.commands.course_block.add_file import (
    AddFileBlockCommandHandler,
)
from learnic.application.commands.course_block.add_multi_choice import (
    AddMultiChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.add_photo_collage import (
    AddPhotoCollageBlockCommandHandler,
)
from learnic.application.commands.course_block.add_rutube_video import (
    AddRutubeVideoBlockCommandHandler,
)
from learnic.application.commands.course_block.add_video_file import (
    AddVideoFileBlockCommandHandler,
)
from learnic.application.commands.course_block.add_single_choice import (
    AddSingleChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.add_text_input import (
    AddTextInputBlockCommandHandler,
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
from learnic.application.commands.course_block.update_file import (
    UpdateFileBlockCommandHandler,
)
from learnic.application.commands.course_block.update_html import (
    UpdateHtmlBlockCommandHandler,
)
from learnic.application.commands.course_block.update_photo_collage import (
    UpdatePhotoCollageBlockCommandHandler,
)
from learnic.application.commands.course_block.update_video_file import (
    UpdateVideoFileBlockCommandHandler,
)
from learnic.application.commands.course_block.update_katex import (
    UpdateKatexBlockCommandHandler,
)
from learnic.application.commands.course_block.update_multi_choice import (
    UpdateMultiChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.update_rutube_video import (
    UpdateRutubeVideoBlockCommandHandler,
)
from learnic.application.commands.course_block.update_single_choice import (
    UpdateSingleChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.update_text_input import (
    UpdateTextInputBlockCommandHandler,
)
from learnic.application.commands.course_draft.reset import (
    ResetCourseDraftCommandHandler,
)
from learnic.application.commands.enrollment.complete import (
    CompleteEnrollmentCommandHandler,
)
from learnic.application.commands.enrollment.enroll_in_course import (
    EnrollStudentInCourseCommandHandler,
)
from learnic.application.commands.enrollment.grant_course import (
    GrantCourseEnrollmentCommandHandler,
)
from learnic.application.commands.enrollment.update_progress import (
    UpdateProgressCommandHandler,
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
from learnic.application.commands.product.add_course import (
    AddCourseProductCommandHandler,
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
from learnic.application.queries.tag.list import (
    ListProductTagsQueryHandler,
)
from learnic.application.queries.tag.popular import (
    GetPopularTagsQueryHandler,
)
from learnic.application.queries.tag.search import (
    SearchTagsQueryHandler,
)
from learnic.application.commands.product.update_tags import (
    UpdateProductTagsCommandHandler,
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
from learnic.application.commands.user.change_portfolio_url import (
    ChangeUserPortfolioUrlCommandHandler,
)
from learnic.application.commands.user.change_public_email import (
    ChangeUserPublicEmailCommandHandler,
)
from learnic.application.commands.user.change_website_url import (
    ChangeUserWebsiteUrlCommandHandler,
)
from learnic.application.commands.user_social_link.set_all import (
    SetUserSocialLinksCommandHandler,
)
from learnic.application.common.persistence.user_social_link import (
    UserSocialLinkGateway,
    UserSocialLinkReader,
)
from learnic.application.queries.user_social_link.list_for_user import (
    ListUserSocialLinksQueryHandler,
)
from learnic.application.commands.user.cover.remove import (
    RemoveUserCoverCommandHandler,
)
from learnic.application.commands.user.cover.set import (
    SetUserCoverCommandHandler,
)
from learnic.application.commands.user_experience.add import (
    AddUserExperienceCommandHandler,
)
from learnic.application.commands.user_experience.delete import (
    DeleteUserExperienceCommandHandler,
)
from learnic.application.commands.user_experience.icon.remove import (
    RemoveUserExperienceIconCommandHandler,
)
from learnic.application.commands.user_experience.icon.set import (
    SetUserExperienceIconCommandHandler,
)
from learnic.application.commands.user_experience.update import (
    UpdateUserExperienceCommandHandler,
)
from learnic.application.common.persistence.user_experience import (
    UserExperienceGateway,
    UserExperienceReader,
)
from learnic.application.queries.user_experience.list_for_user import (
    ListUserExperiencesQueryHandler,
)
from learnic.application.common.email.renderer import EmailRenderer
from learnic.application.common.email.sender import EmailSender
from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.course_content import (
    CourseContentReader,
)
from learnic.application.common.persistence.course_draft import (
    CourseDraftResetter,
)
from learnic.application.common.enrollment.course_strategy import (
    CourseEnrollmentStrategy,
)
from learnic.application.common.enrollment.service import EnrollmentService
from learnic.application.common.enrollment.strategies import (
    EnrollmentStrategy,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
    EnrollmentReader,
)
from learnic.entities.enrollment.enums import EnrollmentKind
from learnic.application.common.persistence.course_lesson import (
    CourseLessonGateway,
)
from learnic.application.common.persistence.course_module import (
    CourseModuleGateway,
)
from learnic.application.common.persistence.course_release import (
    CourseReleaseBlockGateway,
    CourseReleaseGateway,
    CourseReleaseReader,
    CourseReleaseSnapshotter,
)
from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.persistence.billing import (
    AuthorActiveFilesReader,
    FileUsageReader,
    StorageQuotaBreachGateway,
    StorageQuotaLock,
    SubscriptionGateway,
    SubscriptionReader,
)
from learnic.application.common.persistence.file import (
    FilesGateway,
    FilesReader,
)
from learnic.application.commands.billing.reconcile_storage_quotas import (
    ReconcileStorageQuotasCommandHandler,
)
from learnic.application.commands.file.purge_from_storage import (
    PurgeFileFromStorageCommandHandler,
)
from learnic.application.queries.billing.get_course_storage_remaining import (
    GetCourseStorageRemainingQueryHandler,
)
from learnic.application.queries.billing.get_my_subscription import (
    GetMySubscriptionQueryHandler,
)
from learnic.application.common.persistence.product import (
    ProductGateway,
    ProductReader,
)
from learnic.application.common.persistence.product_qa import (
    ProductQAGateway,
    ProductQAReader,
)
from learnic.application.common.notifications.channels import (
    DeliveryChannel,
)
from learnic.application.common.notifications.event_bus import (
    NotificationEventBus,
)
from learnic.application.common.notifications.gateway import (
    NotificationGateway,
)
from learnic.application.common.notifications.kind_spec import (
    NotificationKindRegistry,
)
from learnic.application.common.notifications.notifier import Notifier
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.notifications.reader import (
    NotificationReader,
)
from learnic.entities.notification.enums import NotificationChannel
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
from learnic.application.common.persistence.tag import (
    ProductTagsSaver,
    TagGateway,
    TagReader,
)
from learnic.application.common.persistence.session import SessionsReader
from learnic.application.common.persistence.statistic import (
    StatisticGateway,
)
from learnic.application.common.statistics.collector import (
    StatisticsCollector,
)
from learnic.application.common.statistics.dedupe import StatisticsDedupe
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
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.email_tokens import EmailTokenStore
from learnic.application.common.security.html import HtmlSanitizer
from learnic.application.common.security.passwords import PasswordHasher
from learnic.application.common.security.policies import SecurityPolicies
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.storage.file_uploads import (
    DefaultStorageBucket,
    FileUploadService,
)
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
from learnic.application.queries.product.search import (
    SearchPublishedProductsQueryHandler,
)
from learnic.application.queries.product.get_by_user import (
    GetUserProductsQueryHandler,
)
from learnic.application.queries.product.recommend_for_me import (
    RankingPolicy,
    RankingWeights,
    RecommendForMeQueryHandler,
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
from learnic.application.queries.enrollment.list_for_product import (
    GetProductEnrollmentsQueryHandler,
)
from learnic.application.queries.enrollment.list_for_student import (
    GetStudentEnrollmentsQueryHandler,
)
from learnic.application.queries.product_qa.list import (
    GetProductQAListQueryHandler,
)
from learnic.application.commands.notification_preferences.update import (
    UpdateNotificationPreferencesCommandHandler,
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
    AppConfig,
    ASGIConfig,
    Configs,
    PostgresConfig,
    RecommendationsConfig,
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
    JinjaEmailRenderer,
    build_environment,
)
from learnic.infrastructure.persistence.adapters.email_token import (
    EmailTokenStoreAlchemy,
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
from learnic.infrastructure.persistence.adapters.enrollment import (
    EnrollmentMapperAlchemy,
    EnrollmentReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_lesson import (
    CourseLessonMapperAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_module import (
    CourseModuleMapperAlchemy,
)
from learnic.infrastructure.persistence.adapters.course_release import (
    CourseReleaseBlockGatewayAlchemy,
    CourseReleaseMapperAlchemy,
    CourseReleaseReaderAlchemy,
    CourseReleaseSnapshotterAlchemy,
)
from learnic.infrastructure.persistence.adapters.billing import (
    AuthorActiveFilesReaderAlchemy,
    FileUsageReaderAlchemy,
    StorageQuotaBreachMapperAlchemy,
    StorageQuotaLockAlchemy,
    SubscriptionMapperAlchemy,
    SubscriptionReaderAlchemy,
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
from learnic.infrastructure.notifications.channels.email import EmailChannel
from learnic.infrastructure.notifications.channels.in_app import InAppChannel
from learnic.infrastructure.notifications.channels.web_push import (
    WebPushChannel,
)
from learnic.infrastructure.notifications.event_bus_redis import (
    NotificationEventBusRedis,
)
from learnic.infrastructure.notifications.notifier import NotifierService
from learnic.infrastructure.notifications.specs import default_registry
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
from learnic.infrastructure.persistence.adapters.tag import (
    ProductTagsSaverAlchemy,
    TagMapperAlchemy,
    TagReaderAlchemy,
)
from learnic.infrastructure.auth.authorizer import AuthorizerService
from learnic.infrastructure.auth.confirm_events_redis import (
    ConfirmEventBusRedis,
)
from learnic.infrastructure.auth.product_owner_resolver import (
    ProductOwnerResolverAlchemy,
)
from learnic.infrastructure.persistence.adapters.refresh_token import (
    RefreshTokenStoreAlchemy,
)
from learnic.infrastructure.persistence.adapters.session import (
    SessionsReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.statistic import (
    StatisticMapperAlchemy,
)
from learnic.infrastructure.statistics.collector_alchemy import (
    StatisticsCollectorAlchemy,
)
from learnic.infrastructure.statistics.collector_deduping import (
    DedupingStatisticsCollector,
)
from learnic.infrastructure.statistics.dedupe_redis import (
    StatisticsDedupeRedis,
)
from learnic.infrastructure.statistics.specs import (
    default_registry as default_statistic_registry,
)
from learnic.infrastructure.statistics.specs._spec import (
    StatisticTypeRegistry,
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
from learnic.infrastructure.persistence.adapters.user_social_link import (
    UserSocialLinkMapperAlchemy,
    UserSocialLinkReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.user_experience import (
    UserExperienceMapperAlchemy,
    UserExperienceReaderAlchemy,
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
    def security_policies(self, configs: Configs) -> SecurityPolicies:
        # ``SecurityConfig`` structurally satisfies ``SecurityPolicies``
        # (matching attribute names + types); the explicit ``provides``
        # is what handlers actually depend on so the application layer
        # never imports the concrete config class.
        return configs.security

    @provide
    def web_push_config(self, configs: Configs) -> WebPushConfig:
        return configs.web_push

    @provide
    def app_config(self, configs: Configs) -> AppConfig:
        return configs.app

    @provide
    def recommendations_config(
        self, configs: Configs,
    ) -> RecommendationsConfig:
        return configs.recommendations

    @provide
    def ranking_policy(
        self, recommendations: RecommendationsConfig,
    ) -> RankingPolicy:
        # Same pattern as ``purchase_config``: the env block stays in
        # infrastructure, the application layer depends only on the
        # frozen DTO.
        return RankingPolicy(
            weights=RankingWeights(
                tag=recommendations.weight_tag,
                author=recommendations.weight_author,
                popularity=recommendations.weight_popularity,
                freshness=recommendations.weight_freshness,
            ),
            popularity_window_days=recommendations.popularity_window_days,
        )


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
    subscription_gateway = provide(
        SubscriptionMapperAlchemy,
        provides=SubscriptionGateway,
    )
    subscription_reader = provide(
        SubscriptionReaderAlchemy,
        provides=SubscriptionReader,
    )
    file_usage_reader = provide(
        FileUsageReaderAlchemy,
        provides=FileUsageReader,
    )
    storage_quota_lock = provide(
        StorageQuotaLockAlchemy,
        provides=StorageQuotaLock,
    )
    storage_quota_breach_gateway = provide(
        StorageQuotaBreachMapperAlchemy,
        provides=StorageQuotaBreachGateway,
    )
    author_active_files_reader = provide(
        AuthorActiveFilesReaderAlchemy,
        provides=AuthorActiveFilesReader,
    )
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
    user_experience_gateway = provide(
        UserExperienceMapperAlchemy,
        provides=UserExperienceGateway,
    )
    user_experience_reader = provide(
        UserExperienceReaderAlchemy,
        provides=UserExperienceReader,
    )
    user_social_link_gateway = provide(
        UserSocialLinkMapperAlchemy,
        provides=UserSocialLinkGateway,
    )
    user_social_link_reader = provide(
        UserSocialLinkReaderAlchemy,
        provides=UserSocialLinkReader,
    )
    enrollment_gateway = provide(
        EnrollmentMapperAlchemy,
        provides=EnrollmentGateway,
    )
    enrollment_reader = provide(
        EnrollmentReaderAlchemy,
        provides=EnrollmentReader,
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
    course_release_block_gateway = provide(
        CourseReleaseBlockGatewayAlchemy,
        provides=CourseReleaseBlockGateway,
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
    tag_gateway = provide(
        TagMapperAlchemy,
        provides=TagGateway,
    )
    tag_reader = provide(
        TagReaderAlchemy,
        provides=TagReader,
    )
    product_tags_saver = provide(
        ProductTagsSaverAlchemy,
        provides=ProductTagsSaver,
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
    statistic_gateway = provide(
        StatisticMapperAlchemy,
        provides=StatisticGateway,
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
    file_upload_service = provide(FileUploadService)


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

    @provide
    def default_bucket(self, s3: S3Config) -> DefaultStorageBucket:
        return DefaultStorageBucket(s3.bucket)


class TasksProvider(Provider):
    scope = Scope.REQUEST

    scheduler = provide(TaskSchedulerTaskIQ, provides=TaskScheduler)


class PushProvider(Provider):
    scope = Scope.APP

    sender = provide(PywebpushSender, provides=PushSender)


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

    @provide(scope=Scope.APP)
    def kind_registry(self) -> NotificationKindRegistry:
        return default_registry()


class StatisticsProvider(Provider):
    """DI bindings for the statistics subsystem.

    Adding a new statistic type does not require any change here:
    the new spec is picked up by
    :func:`default_statistic_registry`, the gateway dispatches by
    details class, the dedup filter asks the spec for the key,
    and the collector's Protocol surface is type-agnostic.

    The public ``StatisticsCollector`` is the dedup decorator
    wrapping the inline-write Alchemy collector — every recorded
    event passes through dedup first, then (if the window allows)
    hits the DB. Switching the write path to TaskIQ later means
    swapping ``StatisticsCollectorAlchemy`` for a different inner
    implementation; the dedup wrapper is unchanged.
    """

    scope = Scope.APP

    @provide
    def type_registry(self) -> StatisticTypeRegistry:
        return default_statistic_registry()

    inline_collector = provide(StatisticsCollectorAlchemy)
    dedupe = provide(
        StatisticsDedupeRedis,
        provides=StatisticsDedupe,
    )

    @provide
    def collector(
        self,
        inner: StatisticsCollectorAlchemy,
        dedupe: StatisticsDedupe,
        types: StatisticTypeRegistry,
    ) -> StatisticsCollector:
        return DedupingStatisticsCollector(inner, dedupe, types)


class NotificationChannelsProvider(Provider):
    scope = Scope.REQUEST

    email_channel = provide(EmailChannel)
    push_channel = provide(WebPushChannel)
    in_app_channel = provide(InAppChannel)
    notifier = provide(NotifierService, provides=Notifier)

    @provide
    def channels(
        self,
        email_channel: EmailChannel,
        push_channel: WebPushChannel,
        in_app_channel: InAppChannel,
    ) -> Mapping[NotificationChannel, DeliveryChannel]:
        # Channel registration is here (not in IoC of each spec) because
        # the spec doesn't choose channels — the publisher does. Adding
        # a new channel = a new ``provide(...)`` line above plus a new
        # entry in this mapping; spec classes get the new channel
        # automatically (default :meth:`render` returns ``None`` so
        # uninterested kinds skip it).
        return {
            NotificationChannel.EMAIL: email_channel,
            NotificationChannel.PUSH: push_channel,
            NotificationChannel.IN_APP: in_app_channel,
        }


class EnrollmentStrategiesProvider(Provider):
    """Plug-in registry of per-product-kind enrollment strategies.

    Same shape as :class:`NotificationChannelsProvider`. Adding a
    new ``EnrollmentKind`` means:

    1. Write a new ``EnrollmentStrategy`` impl alongside
       ``CourseEnrollmentStrategy``.
    2. Add it to ``_DECLARED_STRATEGIES`` in
       ``application/common/enrollment/strategies.py`` (module-load
       fail-fast).
    3. Add a ``provide(...)`` line below and an entry to
       :meth:`strategies` — the runtime fail-fast guards against
       forgetting this step.

    The service itself (``EnrollmentService``) never changes.
    """

    scope = Scope.REQUEST

    course_strategy = provide(CourseEnrollmentStrategy)
    enrollment_service = provide(EnrollmentService)

    @provide
    def strategies(
        self,
        course: CourseEnrollmentStrategy,
    ) -> Mapping[EnrollmentKind, EnrollmentStrategy]:
        mapping: dict[EnrollmentKind, EnrollmentStrategy] = {
            EnrollmentKind.COURSE: course,
        }
        missing = set(EnrollmentKind) - mapping.keys()
        if missing:
            raise RuntimeError(
                "EnrollmentStrategy registry incomplete; missing: "
                f"{sorted(k.value for k in missing)}",
            )
        return mapping


class ConfirmEventsProvider(Provider):
    scope = Scope.APP

    event_bus = provide(ConfirmEventBusRedis, provides=ConfirmEventBus)


class InteractorsProvider(Provider):
    scope = Scope.REQUEST

    get_user = provide(GetUserQueryHandler)
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
    change_user_website_url = provide(ChangeUserWebsiteUrlCommandHandler)
    change_user_portfolio_url = provide(ChangeUserPortfolioUrlCommandHandler)
    change_user_public_email = provide(ChangeUserPublicEmailCommandHandler)

    set_user_social_links = provide(SetUserSocialLinksCommandHandler)
    list_user_social_links = provide(ListUserSocialLinksQueryHandler)

    add_user_experience = provide(AddUserExperienceCommandHandler)
    update_user_experience = provide(UpdateUserExperienceCommandHandler)
    delete_user_experience = provide(DeleteUserExperienceCommandHandler)
    set_user_experience_icon = provide(SetUserExperienceIconCommandHandler)
    remove_user_experience_icon = provide(
        RemoveUserExperienceIconCommandHandler,
    )
    list_user_experiences = provide(ListUserExperiencesQueryHandler)

    add_course_product = provide(AddCourseProductCommandHandler)
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
    get_product = provide(GetProductQueryHandler)
    get_my_products = provide(GetMyProductsQueryHandler)
    get_published_products = provide(GetPublishedProductsQueryHandler)
    search_published_products = provide(
        SearchPublishedProductsQueryHandler,
    )
    get_user_products = provide(GetUserProductsQueryHandler)
    recommend_for_me = provide(RecommendForMeQueryHandler)
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

    enroll_student_in_course = provide(
        EnrollStudentInCourseCommandHandler,
    )
    grant_course_enrollment = provide(
        GrantCourseEnrollmentCommandHandler,
    )
    update_progress = provide(UpdateProgressCommandHandler)
    complete_enrollment = provide(CompleteEnrollmentCommandHandler)
    get_product_enrollments = provide(GetProductEnrollmentsQueryHandler)
    get_student_enrollments = provide(GetStudentEnrollmentsQueryHandler)

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
    add_single_choice_block = provide(AddSingleChoiceBlockCommandHandler)
    add_multi_choice_block = provide(AddMultiChoiceBlockCommandHandler)
    add_text_input_block = provide(AddTextInputBlockCommandHandler)
    add_file_block = provide(AddFileBlockCommandHandler)
    add_video_file_block = provide(AddVideoFileBlockCommandHandler)
    add_photo_collage_block = provide(AddPhotoCollageBlockCommandHandler)
    update_html_block = provide(UpdateHtmlBlockCommandHandler)
    update_katex_block = provide(UpdateKatexBlockCommandHandler)
    update_rutube_video_block = provide(UpdateRutubeVideoBlockCommandHandler)
    update_code_block = provide(UpdateCodeBlockCommandHandler)
    update_single_choice_block = provide(UpdateSingleChoiceBlockCommandHandler)
    update_multi_choice_block = provide(UpdateMultiChoiceBlockCommandHandler)
    update_text_input_block = provide(UpdateTextInputBlockCommandHandler)
    update_file_block = provide(UpdateFileBlockCommandHandler)
    update_video_file_block = provide(UpdateVideoFileBlockCommandHandler)
    update_photo_collage_block = provide(UpdatePhotoCollageBlockCommandHandler)
    entitlement_service = provide(EntitlementService)
    get_my_subscription = provide(GetMySubscriptionQueryHandler)
    get_course_storage_remaining = provide(
        GetCourseStorageRemainingQueryHandler,
    )
    reconcile_storage_quotas = provide(
        ReconcileStorageQuotasCommandHandler,
    )
    purge_file_from_storage = provide(
        PurgeFileFromStorageCommandHandler,
    )
    check_block_answer = provide(CheckBlockAnswerCommandHandler)
    reveal_block_answer = provide(RevealBlockAnswerCommandHandler)
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

    search_tags = provide(SearchTagsQueryHandler)
    list_product_tags = provide(ListProductTagsQueryHandler)
    get_popular_tags = provide(GetPopularTagsQueryHandler)
    update_product_tags = provide(UpdateProductTagsCommandHandler)

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
        return JinjaEmailRenderer(env=env)

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


def setup_providers(configs: Configs) -> AsyncContainer:
    return make_async_container(
        ConfigsProvider(),
        DBProvider(),
        GatewaysProvider(),
        SecurityProvider(),
        S3Provider(),
        TasksProvider(),
        PushProvider(),
        RedisProvider(),
        PresenceProvider(),
        CollaborationProvider(),
        ProductEventsProvider(),
        NotificationEventsProvider(),
        NotificationChannelsProvider(),
        StatisticsProvider(),
        EnrollmentStrategiesProvider(),
        ConfirmEventsProvider(),
        EmailProvider(),
        InteractorsProvider(),
        context={Configs: configs},
    )
