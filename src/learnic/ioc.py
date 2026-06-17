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
    provide_all,
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
from learnic.application.commands.auth.purge_unverified_users import (
    PurgeUnverifiedUsersCommandHandler,
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
from learnic.application.commands.note_block.add_code import (
    AddCodeBlockCommandHandler,
)
from learnic.application.commands.note_block.add_function_graph import (
    AddFunctionGraphBlockCommandHandler,
)
from learnic.application.commands.note_block.update_function_graph import (
    UpdateFunctionGraphBlockCommandHandler,
)
from learnic.application.commands.blog_post.change_slug import (
    ChangeBlogPostSlugCommandHandler,
)
from learnic.application.commands.blog_post.cover.remove import (
    RemoveBlogPostCoverCommandHandler,
)
from learnic.application.commands.blog_post.cover.set import (
    SetBlogPostCoverCommandHandler,
)
from learnic.application.commands.blog_post.create import (
    CreateBlogPostCommandHandler,
)
from learnic.application.commands.blog_post.delete import (
    DeleteBlogPostCommandHandler,
)
from learnic.application.commands.blog_post.edit_meta import (
    EditBlogPostMetaCommandHandler,
)
from learnic.application.commands.blog_post.publish import (
    PublishBlogPostCommandHandler,
)
from learnic.application.commands.blog_post.rename import (
    RenameBlogPostCommandHandler,
)
from learnic.application.commands.blog_post.unpublish import (
    UnpublishBlogPostCommandHandler,
)
from learnic.application.commands.blog_post_block.add_html import (
    AddBlogHtmlBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.add_image import (
    AddBlogImageBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.add_video import (
    AddBlogVideoBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.delete import (
    DeleteBlogPostBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.reorder import (
    ReorderBlogPostBlocksCommandHandler,
)
from learnic.application.commands.blog_post_block.update_html import (
    UpdateBlogHtmlBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.update_image import (
    UpdateBlogImageBlockCommandHandler,
)
from learnic.application.commands.blog_post_block.update_video import (
    UpdateBlogVideoBlockCommandHandler,
)
from learnic.application.commands.note_block.check_answer import (
    CheckBlockAnswerCommandHandler,
)
from learnic.application.commands.note_block.reveal_answer import (
    RevealBlockAnswerCommandHandler,
)
from learnic.application.queries.note_block_answer.list_mine import (
    ListMyBlockAnswersQueryHandler,
)
from learnic.application.commands.note_block.add_html import (
    AddHtmlBlockCommandHandler,
)
from learnic.application.commands.note_block.add_katex import (
    AddKatexBlockCommandHandler,
)
from learnic.application.commands.note_block.add_file import (
    AddFileBlockCommandHandler,
)
from learnic.application.commands.note_block.add_multi_choice import (
    AddMultiChoiceBlockCommandHandler,
)
from learnic.application.commands.note_block.add_photo_collage import (
    AddPhotoCollageBlockCommandHandler,
)
from learnic.application.commands.note_block.add_rutube_video import (
    AddRutubeVideoBlockCommandHandler,
)
from learnic.application.commands.note_block.add_video_file import (
    AddVideoFileBlockCommandHandler,
)
from learnic.application.commands.note_block.add_single_choice import (
    AddSingleChoiceBlockCommandHandler,
)
from learnic.application.commands.note_block.add_text_input import (
    AddTextInputBlockCommandHandler,
)
from learnic.application.commands.note_block.delete import (
    DeleteLessonBlockCommandHandler,
)
from learnic.application.commands.note_block.reorder import (
    ReorderLessonBlocksCommandHandler,
)
from learnic.application.commands.note_block.update_code import (
    UpdateCodeBlockCommandHandler,
)
from learnic.application.commands.note_block.update_file import (
    UpdateFileBlockCommandHandler,
)
from learnic.application.commands.note_block.update_html import (
    UpdateHtmlBlockCommandHandler,
)
from learnic.application.commands.note_block.add_photo_collage_item import (
    AddPhotoCollageItemCommandHandler,
)
from learnic.application.commands.note_block.remove_photo_collage_item import (
    RemovePhotoCollageItemCommandHandler,
)
from learnic.application.commands.note_block.reorder_photo_collage_items import (
    ReorderPhotoCollageItemsCommandHandler,
)
from learnic.application.commands.note_block.update_photo_collage_item_caption import (  # noqa: E501
    UpdatePhotoCollageItemCaptionCommandHandler,
)
from learnic.application.commands.note_block.update_photo_collage_title import (
    UpdatePhotoCollageTitleCommandHandler,
)
from learnic.application.commands.note_block.update_video_file import (
    UpdateVideoFileBlockCommandHandler,
)
from learnic.application.commands.note_block.update_katex import (
    UpdateKatexBlockCommandHandler,
)
from learnic.application.commands.note_block.update_multi_choice import (
    UpdateMultiChoiceBlockCommandHandler,
)
from learnic.application.commands.note_block.update_rutube_video import (
    UpdateRutubeVideoBlockCommandHandler,
)
from learnic.application.commands.note_block.update_single_choice import (
    UpdateSingleChoiceBlockCommandHandler,
)
from learnic.application.commands.note_block.update_text_input import (
    UpdateTextInputBlockCommandHandler,
)
from learnic.application.commands.note_draft.reset import (
    ResetNoteDraftCommandHandler,
)
from learnic.application.commands.enrollment.complete import (
    CompleteEnrollmentCommandHandler,
)
from learnic.application.commands.enrollment.enroll_into_product import (
    EnrollIntoProductCommandHandler,
)
from learnic.application.commands.enrollment.repin import (
    RePinNoteEnrollmentCommandHandler,
)
from learnic.application.commands.enrollment.self_repin import (
    SelfRePinNoteEnrollmentCommandHandler,
)
from learnic.application.commands.note_lesson.add import (
    AddNoteLessonCommandHandler,
)
from learnic.application.commands.note_lesson.delete import (
    DeleteNoteLessonCommandHandler,
)
from learnic.application.commands.note_lesson.move import (
    MoveNoteLessonCommandHandler,
)
from learnic.application.commands.note_lesson.rename import (
    RenameNoteLessonCommandHandler,
)
from learnic.application.commands.note_lesson.reorder import (
    ReorderNoteLessonsCommandHandler,
)
from learnic.application.commands.note_module.add import (
    AddNoteModuleCommandHandler,
)
from learnic.application.commands.note_module.delete import (
    DeleteNoteModuleCommandHandler,
)
from learnic.application.commands.note_module.rename import (
    RenameNoteModuleCommandHandler,
)
from learnic.application.commands.note_module.reorder import (
    ReorderNoteModulesCommandHandler,
)
from learnic.application.commands.note_module.update_description import (
    UpdateNoteModuleDescriptionCommandHandler,
)
from learnic.application.commands.note_release.create import (
    CreateNoteReleaseCommandHandler,
)
from learnic.application.commands.product.add_note import (
    AddNoteProductCommandHandler,
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
from learnic.application.commands.product.change_visibility import (
    ChangeProductVisibilityCommandHandler,
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
from learnic.application.commands.product_collaboration.purge_expired_invites import (  # noqa: E501
    PurgeExpiredInvitesCommandHandler,
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
from learnic.application.commands.product_gift.accept import (
    AcceptGiftByTokenCommandHandler,
)
from learnic.application.commands.product_gift.accept_in_app import (
    AcceptGiftInAppCommandHandler,
)
from learnic.application.commands.product_gift.decline_in_app import (
    DeclineGiftCommandHandler,
)
from learnic.application.commands.product_gift.invite_by_email import (
    InviteGiftByEmailCommandHandler,
)
from learnic.application.commands.product_gift.invite_by_user import (
    InviteGiftByUserCommandHandler,
)
from learnic.application.commands.product_gift.purge_expired_invites import (
    PurgeExpiredGiftsCommandHandler,
)
from learnic.application.commands.product_gift.revoke import (
    RevokeGiftCommandHandler,
)
from learnic.application.queries.product_gift.get_gift import (
    GetGiftQueryHandler,
)
from learnic.application.queries.product_gift.list_for_product import (
    ListProductGiftsQueryHandler,
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
from learnic.application.common.email.anon_rate_limit import (
    AnonymousEmailRateLimiter,
)
from learnic.application.common.email.renderer import EmailRenderer
from learnic.application.common.email.sender import EmailSender
from learnic.application.common.persistence.blog_post import (
    BlogPostGateway,
    BlogPostReader,
)
from learnic.application.common.persistence.blog_post_block import (
    BlogPostBlockGateway,
)
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.note_content import (
    NoteContentReader,
)
from learnic.application.common.persistence.note_draft import (
    NoteDraftResetter,
)
from learnic.application.common.enrollment.note_strategy import (
    NoteEnrollmentStrategy,
)
from learnic.application.common.enrollment.service import EnrollmentService
from learnic.application.common.enrollment.strategies import (
    EnrollmentStrategy,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
    EnrollmentReader,
)
from learnic.application.common.persistence.note_block_answer import (
    NoteBlockAnswerGateway,
    NoteBlockAnswerReader,
)
from learnic.entities.enrollment.enums import EnrollmentKind
from learnic.application.common.persistence.note_lesson import (
    NoteLessonGateway,
)
from learnic.application.common.persistence.note_module import (
    NoteModuleGateway,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseBlockGateway,
    NoteReleaseGateway,
    NoteReleaseReader,
    NoteReleaseSnapshotter,
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
from learnic.application.common.persistence.scheduler_lock import (
    GlobalSchedulerLock,
)
from learnic.application.common.persistence.file import (
    FilesGateway,
    FilesReader,
)
from learnic.application.commands.billing.grant_subscription import (
    GrantSubscriptionCommandHandler,
)
from learnic.application.commands.billing.reconcile_storage_quotas import (
    ReconcileStorageQuotasCommandHandler,
)
from learnic.application.commands.billing.revoke_subscription import (
    RevokeSubscriptionCommandHandler,
)
from learnic.application.commands.file.purge_from_storage import (
    PurgeFileFromStorageCommandHandler,
)
from learnic.application.queries.billing.get_note_storage import (
    GetNoteStorageQueryHandler,
)
from learnic.application.queries.billing.get_note_storage_remaining import (
    GetNoteStorageRemainingQueryHandler,
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
from learnic.application.common.storage_quota.event_bus import (
    StorageQuotaEventBus,
)
from learnic.application.common.storage_quota.publisher import (
    StorageQuotaUsagePublisher,
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
from learnic.application.common.persistence.email_sending import (
    EmailSendingGateway,
)
from learnic.application.common.persistence.product_gift import (
    ProductGiftGateway,
    ProductGiftReader,
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
from learnic.application.common.cursors.event_bus import CursorsEventBus
from learnic.application.common.cursors.state import CursorsState
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
from learnic.application.common.email.rate_limit import (
    EmailSendRateLimiter,
)
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
from learnic.application.commands.admin.ban_user import (
    BanUserCommandHandler,
)
from learnic.application.commands.admin.delete_note import (
    AdminDeleteNoteCommandHandler,
)
from learnic.application.commands.admin.grant_admin import (
    GrantAdminCommandHandler,
)
from learnic.application.commands.admin.unban_user import (
    UnbanUserCommandHandler,
)
from learnic.application.queries.admin.get_metric_series import (
    GetAdminMetricSeriesQueryHandler,
)
from learnic.application.queries.admin.get_stats import (
    GetAdminStatsQueryHandler,
)
from learnic.application.common.persistence.admin_metrics import (
    AdminMetricsReader,
)
from learnic.application.common.persistence.admin_stats import (
    AdminStatsReader,
)
from learnic.application.common.persistence.teacher_ranking import (
    TeacherRankingReader,
)
from learnic.application.queries.user.admins import (
    GetAdminsQueryHandler,
)
from learnic.application.queries.user.get import GetUserQueryHandler
from learnic.application.queries.user.get_admin_status import (
    GetMyAdminStatusQueryHandler,
)
from learnic.application.queries.user.search import (
    SearchUsersQueryHandler,
)
from learnic.application.queries.user.top_teachers import (
    GetTopTeachersQueryHandler,
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
from learnic.application.queries.product.search_my import (
    SearchMyProductsQueryHandler,
)
from learnic.application.queries.product.get_by_user import (
    GetUserProductsQueryHandler,
)
from learnic.application.queries.product.recommend_for_me import (
    RankingPolicy,
    RankingWeights,
    RecommendForMeQueryHandler,
)
from learnic.application.queries.note_content.get_block import (
    GetLessonBlockQueryHandler,
)
from learnic.application.queries.note_content.get_draft import (
    GetNoteDraftQueryHandler,
)
from learnic.application.queries.blog_post.get import (
    GetBlogPostQueryHandler,
)
from learnic.application.queries.blog_post.get_block import (
    GetBlogPostBlockQueryHandler,
)
from learnic.application.queries.blog_post.get_by_slug import (
    GetPublishedBlogPostBySlugQueryHandler,
)
from learnic.application.queries.blog_post.list import (
    ListBlogPostsQueryHandler,
)
from learnic.application.queries.blog_post.list_published import (
    ListPublishedBlogPostsQueryHandler,
)
from learnic.application.queries.note_content.get_release_lesson import (
    GetReleaseLessonQueryHandler,
)
from learnic.application.queries.note_content.get_scheme import (
    GetNoteSchemeQueryHandler,
)
from learnic.application.queries.note_content.search_content import (
    SearchNoteContentQueryHandler,
)
from learnic.application.queries.note_release.get_content import (
    GetNoteReleaseContentQueryHandler,
)
from learnic.application.queries.note_release.list_for_product import (
    ListNoteReleasesQueryHandler,
)
from learnic.application.queries.enrollment.list_for_product import (
    GetProductEnrollmentsQueryHandler,
)
from learnic.application.queries.enrollment.list_for_student import (
    GetStudentEnrollmentsQueryHandler,
)
from learnic.application.queries.enrollment.list_releases import (
    ListEnrollmentReleasesQueryHandler,
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
from learnic.infrastructure.persistence.adapters.blog_post import (
    BlogPostMapperAlchemy,
    BlogPostReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.blog_post_block import (
    BlogPostBlockGatewayAlchemy,
)
from learnic.infrastructure.persistence.adapters.note_block import (
    LessonBlockGatewayAlchemy,
)
from learnic.infrastructure.persistence.adapters.note_content import (
    NoteContentReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.note_draft import (
    NoteDraftResetterAlchemy,
)
from learnic.infrastructure.persistence.adapters.enrollment import (
    EnrollmentMapperAlchemy,
    EnrollmentReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.note_block_answer import (
    NoteBlockAnswerMapperAlchemy,
    NoteBlockAnswerReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.note_lesson import (
    NoteLessonMapperAlchemy,
)
from learnic.infrastructure.persistence.adapters.note_module import (
    NoteModuleMapperAlchemy,
)
from learnic.infrastructure.persistence.adapters.note_release import (
    NoteReleaseBlockGatewayAlchemy,
    NoteReleaseMapperAlchemy,
    NoteReleaseReaderAlchemy,
    NoteReleaseSnapshotterAlchemy,
)
from learnic.infrastructure.persistence.adapters.billing import (
    AuthorActiveFilesReaderAlchemy,
    FileUsageReaderAlchemy,
    StorageQuotaBreachMapperAlchemy,
    StorageQuotaLockAlchemy,
    SubscriptionMapperAlchemy,
    SubscriptionReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.scheduler_lock import (
    GlobalSchedulerLockAlchemy,
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
from learnic.infrastructure.storage_quota.event_bus_redis import (
    StorageQuotaEventBusRedis,
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
from learnic.infrastructure.push.sender_webpush import (
    PushHttpClient,
    WebPushSender,
)
from learnic.infrastructure.push.vapid import (
    VapidPublicKey,
    application_server_key,
)
from learnic.infrastructure.persistence.adapters.product_collaboration import (
    ProductCollaborationMapperAlchemy,
    ProductCollaborationReaderAlchemy,
    ProductCollaborationSaverAlchemy,
)
from learnic.infrastructure.persistence.adapters.email_sending import (
    EmailSendingMapperAlchemy,
)
from learnic.infrastructure.persistence.adapters.product_gift import (
    ProductGiftMapperAlchemy,
    ProductGiftReaderAlchemy,
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
from learnic.infrastructure.email.anon_rate_limit_redis import (
    AnonymousEmailRateLimiterRedis,
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
from learnic.infrastructure.persistence.adapters.admin_metrics import (
    AdminMetricsReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.admin_stats import (
    AdminStatsReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.teacher_ranking import (
    TeacherRankingReaderAlchemy,
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
from learnic.infrastructure.cursors.adapters.event_bus_redis import (
    CursorsEventBusRedis,
)
from learnic.infrastructure.cursors.adapters.state_redis import (
    CursorsStateRedis,
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
from learnic.presentation.http.common.admin_deps import AdminAuthenticator
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
    admin_stats_reader = provide(
        AdminStatsReaderAlchemy,
        provides=AdminStatsReader,
    )
    teacher_ranking_reader = provide(
        TeacherRankingReaderAlchemy,
        provides=TeacherRankingReader,
    )
    admin_metrics_reader = provide(
        AdminMetricsReaderAlchemy,
        provides=AdminMetricsReader,
    )
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
    global_scheduler_lock = provide(
        GlobalSchedulerLockAlchemy,
        provides=GlobalSchedulerLock,
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
    note_block_answer_gateway = provide(
        NoteBlockAnswerMapperAlchemy,
        provides=NoteBlockAnswerGateway,
    )
    note_block_answer_reader = provide(
        NoteBlockAnswerReaderAlchemy,
        provides=NoteBlockAnswerReader,
    )
    note_module_gateway = provide(
        NoteModuleMapperAlchemy,
        provides=NoteModuleGateway,
    )
    note_lesson_gateway = provide(
        NoteLessonMapperAlchemy,
        provides=NoteLessonGateway,
    )
    note_content_reader = provide(
        NoteContentReaderAlchemy,
        provides=NoteContentReader,
    )
    lesson_block_gateway = provide(
        LessonBlockGatewayAlchemy,
        provides=LessonBlockGateway,
    )
    blog_post_gateway = provide(
        BlogPostMapperAlchemy,
        provides=BlogPostGateway,
    )
    blog_post_reader = provide(
        BlogPostReaderAlchemy,
        provides=BlogPostReader,
    )
    blog_post_block_gateway = provide(
        BlogPostBlockGatewayAlchemy,
        provides=BlogPostBlockGateway,
    )
    note_release_gateway = provide(
        NoteReleaseMapperAlchemy,
        provides=NoteReleaseGateway,
    )
    note_release_snapshotter = provide(
        NoteReleaseSnapshotterAlchemy,
        provides=NoteReleaseSnapshotter,
    )
    note_release_reader = provide(
        NoteReleaseReaderAlchemy,
        provides=NoteReleaseReader,
    )
    note_release_block_gateway = provide(
        NoteReleaseBlockGatewayAlchemy,
        provides=NoteReleaseBlockGateway,
    )
    note_draft_resetter = provide(
        NoteDraftResetterAlchemy,
        provides=NoteDraftResetter,
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
    product_gift_gateway = provide(
        ProductGiftMapperAlchemy,
        provides=ProductGiftGateway,
    )
    product_gift_reader = provide(
        ProductGiftReaderAlchemy,
        provides=ProductGiftReader,
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
    email_sending_gateway = provide(
        EmailSendingMapperAlchemy,
        provides=EmailSendingGateway,
    )
    email_send_rate_limiter = provide(EmailSendRateLimiter)


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
    admin_authenticator = provide(AdminAuthenticator, scope=Scope.REQUEST)


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

    @provide
    async def http_client(self) -> AsyncIterator[PushHttpClient]:
        # Explicit timeout is the whole point of this client: a stalled
        # push service must not block the worker indefinitely.
        client = httpx.AsyncClient(timeout=10.0)
        try:
            yield PushHttpClient(client)
        finally:
            await client.aclose()

    @provide
    def vapid_public_key(self, config: WebPushConfig) -> VapidPublicKey:
        # Derived from the private key — single source of truth, so the
        # served key can never drift from the one the backend signs with.
        return VapidPublicKey(
            application_server_key(config.vapid_private_key),
        )

    sender = provide(WebPushSender, provides=PushSender)


class RedisProvider(Provider):
    scope = Scope.APP

    anon_email_rate_limiter = provide(
        AnonymousEmailRateLimiterRedis,
        provides=AnonymousEmailRateLimiter,
    )

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


class CursorsProvider(Provider):
    scope = Scope.APP

    event_bus = provide(CursorsEventBusRedis, provides=CursorsEventBus)
    state = provide(CursorsStateRedis, provides=CursorsState)


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
       ``NoteEnrollmentStrategy``.
    2. Add it to ``_DECLARED_STRATEGIES`` in
       ``application/common/enrollment/strategies.py`` (module-load
       fail-fast).
    3. Add a ``provide(...)`` line below and an entry to
       :meth:`strategies` — the runtime fail-fast guards against
       forgetting this step.

    The service itself (``EnrollmentService``) never changes.
    """

    scope = Scope.REQUEST

    note_strategy = provide(NoteEnrollmentStrategy)
    enrollment_service = provide(EnrollmentService)

    @provide
    def strategies(
        self,
        note: NoteEnrollmentStrategy,
    ) -> Mapping[EnrollmentKind, EnrollmentStrategy]:
        mapping: dict[EnrollmentKind, EnrollmentStrategy] = {
            EnrollmentKind.NOTE: note,
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


class StorageQuotaEventsProvider(Provider):
    scope = Scope.APP

    event_bus = provide(
        StorageQuotaEventBusRedis,
        provides=StorageQuotaEventBus,
    )


class InteractorsProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(
        GrantAdminCommandHandler,
        BanUserCommandHandler,
        UnbanUserCommandHandler,
        AdminDeleteNoteCommandHandler,
        GetAdminStatsQueryHandler,
        GetAdminMetricSeriesQueryHandler,
        GetUserQueryHandler,
        GetMyAdminStatusQueryHandler,
        SearchUsersQueryHandler,
        GetTopTeachersQueryHandler,
        GetAdminsQueryHandler,
        GetUserPresenceQueryHandler,
        GetUsersPresenceQueryHandler,
        RegisterCommandHandler,
        LoginCommandHandler,
        RefreshCommandHandler,
        LogoutCommandHandler,
        LogoutAllCommandHandler,
        VerifyEmailCommandHandler,
        VerifyWaitCommandHandler,
        VerifyTokenCommandHandler,
        ResendVerificationCommandHandler,
        PurgeUnverifiedUsersCommandHandler,
        GetTokenStatusQueryHandler,
        RequestPasswordResetCommandHandler,
        ResetPasswordCommandHandler,
        ListMySessionsQueryHandler,
        RevokeSessionCommandHandler,
        SetUserAvatarCommandHandler,
        RemoveUserAvatarCommandHandler,
        SetUserCoverCommandHandler,
        RemoveUserCoverCommandHandler,
        ChangeUserFirstNameCommandHandler,
        ChangeUserLastNameCommandHandler,
        ChangeUserPatronymicCommandHandler,
        ChangeUserDescriptionCommandHandler,
        ChangeUserWebsiteUrlCommandHandler,
        ChangeUserPortfolioUrlCommandHandler,
        ChangeUserPublicEmailCommandHandler,
        SetUserSocialLinksCommandHandler,
        ListUserSocialLinksQueryHandler,
        AddUserExperienceCommandHandler,
        UpdateUserExperienceCommandHandler,
        DeleteUserExperienceCommandHandler,
        SetUserExperienceIconCommandHandler,
        RemoveUserExperienceIconCommandHandler,
        ListUserExperiencesQueryHandler,
        AddNoteProductCommandHandler,
        ChangeProductNameCommandHandler,
        ChangeProductDescriptionCommandHandler,
        ChangeProductDurationCommandHandler,
        ChangeProductVisibilityCommandHandler,
        SetProductCoverCommandHandler,
        RemoveProductCoverCommandHandler,
        PublishProductCommandHandler,
        ArchiveProductCommandHandler,
        UnarchiveProductCommandHandler,
        DeleteProductCommandHandler,
        GetProductQueryHandler,
        GetMyProductsQueryHandler,
        SearchMyProductsQueryHandler,
        GetPublishedProductsQueryHandler,
        SearchPublishedProductsQueryHandler,
        GetUserProductsQueryHandler,
        RecommendForMeQueryHandler,
        CheckProductNameAvailabilityQueryHandler,
        AddProductQACommandHandler,
        ChangeProductQAQuestionCommandHandler,
        ChangeProductQAAnswerCommandHandler,
        ReorderProductQACommandHandler,
        DeleteProductQACommandHandler,
        GetProductQAListQueryHandler,
        EnrollIntoProductCommandHandler,
        CompleteEnrollmentCommandHandler,
        RePinNoteEnrollmentCommandHandler,
        SelfRePinNoteEnrollmentCommandHandler,
        GetProductEnrollmentsQueryHandler,
        GetStudentEnrollmentsQueryHandler,
        ListEnrollmentReleasesQueryHandler,
        AddNoteModuleCommandHandler,
        RenameNoteModuleCommandHandler,
        UpdateNoteModuleDescriptionCommandHandler,
        ReorderNoteModulesCommandHandler,
        DeleteNoteModuleCommandHandler,
        AddNoteLessonCommandHandler,
        RenameNoteLessonCommandHandler,
        MoveNoteLessonCommandHandler,
        ReorderNoteLessonsCommandHandler,
        DeleteNoteLessonCommandHandler,
        AddHtmlBlockCommandHandler,
        AddKatexBlockCommandHandler,
        AddRutubeVideoBlockCommandHandler,
        AddCodeBlockCommandHandler,
        AddFunctionGraphBlockCommandHandler,
        UpdateFunctionGraphBlockCommandHandler,
        AddSingleChoiceBlockCommandHandler,
        AddMultiChoiceBlockCommandHandler,
        AddTextInputBlockCommandHandler,
        AddFileBlockCommandHandler,
        AddVideoFileBlockCommandHandler,
        AddPhotoCollageBlockCommandHandler,
        UpdateHtmlBlockCommandHandler,
        UpdateKatexBlockCommandHandler,
        UpdateRutubeVideoBlockCommandHandler,
        UpdateCodeBlockCommandHandler,
        UpdateSingleChoiceBlockCommandHandler,
        UpdateMultiChoiceBlockCommandHandler,
        UpdateTextInputBlockCommandHandler,
        UpdateFileBlockCommandHandler,
        UpdateVideoFileBlockCommandHandler,
        AddPhotoCollageItemCommandHandler,
        RemovePhotoCollageItemCommandHandler,
        ReorderPhotoCollageItemsCommandHandler,
        UpdatePhotoCollageItemCaptionCommandHandler,
        UpdatePhotoCollageTitleCommandHandler,
        EntitlementService,
        StorageQuotaUsagePublisher,
        GetMySubscriptionQueryHandler,
        GetNoteStorageRemainingQueryHandler,
        GetNoteStorageQueryHandler,
        GrantSubscriptionCommandHandler,
        RevokeSubscriptionCommandHandler,
        ReconcileStorageQuotasCommandHandler,
        PurgeFileFromStorageCommandHandler,
        CheckBlockAnswerCommandHandler,
        RevealBlockAnswerCommandHandler,
        ListMyBlockAnswersQueryHandler,
        ReorderLessonBlocksCommandHandler,
        DeleteLessonBlockCommandHandler,
        GetNoteDraftQueryHandler,
        CreateBlogPostCommandHandler,
        RenameBlogPostCommandHandler,
        EditBlogPostMetaCommandHandler,
        ChangeBlogPostSlugCommandHandler,
        PublishBlogPostCommandHandler,
        UnpublishBlogPostCommandHandler,
        DeleteBlogPostCommandHandler,
        SetBlogPostCoverCommandHandler,
        RemoveBlogPostCoverCommandHandler,
        AddBlogHtmlBlockCommandHandler,
        AddBlogImageBlockCommandHandler,
        AddBlogVideoBlockCommandHandler,
        UpdateBlogHtmlBlockCommandHandler,
        UpdateBlogImageBlockCommandHandler,
        UpdateBlogVideoBlockCommandHandler,
        DeleteBlogPostBlockCommandHandler,
        ReorderBlogPostBlocksCommandHandler,
        GetBlogPostQueryHandler,
        GetBlogPostBlockQueryHandler,
        GetPublishedBlogPostBySlugQueryHandler,
        ListBlogPostsQueryHandler,
        ListPublishedBlogPostsQueryHandler,
        GetLessonBlockQueryHandler,
        GetNoteSchemeQueryHandler,
        GetReleaseLessonQueryHandler,
        SearchNoteContentQueryHandler,
        CreateNoteReleaseCommandHandler,
        ListNoteReleasesQueryHandler,
        GetNoteReleaseContentQueryHandler,
        ResetNoteDraftCommandHandler,
        CreateCustomRoleCommandHandler,
        UpdateCustomRoleCommandHandler,
        DeleteCustomRoleCommandHandler,
        ListProductRolesQueryHandler,
        GetRoleQueryHandler,
        SearchTagsQueryHandler,
        ListProductTagsQueryHandler,
        GetPopularTagsQueryHandler,
        UpdateProductTagsCommandHandler,
        InviteCollaboratorByUserCommandHandler,
        InviteCollaboratorByEmailCommandHandler,
        AcceptCollaborationInviteCommandHandler,
        AcceptCollaborationInAppCommandHandler,
        DeclineCollaborationInAppCommandHandler,
        UpdateCollaborationGrantsCommandHandler,
        RevokeCollaborationCommandHandler,
        ReinviteCollaboratorCommandHandler,
        LeaveProductCommandHandler,
        PurgeExpiredInvitesCommandHandler,
        InviteGiftByUserCommandHandler,
        InviteGiftByEmailCommandHandler,
        AcceptGiftByTokenCommandHandler,
        AcceptGiftInAppCommandHandler,
        DeclineGiftCommandHandler,
        RevokeGiftCommandHandler,
        PurgeExpiredGiftsCommandHandler,
        GetGiftQueryHandler,
        ListProductGiftsQueryHandler,
        ListProductCollaboratorsQueryHandler,
        ListMyCollaborationsQueryHandler,
        GetMyEffectivePermissionsQueryHandler,
        ListMyNotificationsQueryHandler,
        GetMyNotificationCountersQueryHandler,
        MarkNotificationAsReadCommandHandler,
        MarkAllNotificationsAsReadCommandHandler,
        SubscribePushCommandHandler,
        UnsubscribePushCommandHandler,
        ListMyPushSubscriptionsQueryHandler,
        GetMyNotificationPreferencesQueryHandler,
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
        CursorsProvider(),
        CollaborationProvider(),
        ProductEventsProvider(),
        NotificationEventsProvider(),
        StorageQuotaEventsProvider(),
        NotificationChannelsProvider(),
        StatisticsProvider(),
        EnrollmentStrategiesProvider(),
        ConfirmEventsProvider(),
        EmailProvider(),
        InteractorsProvider(),
        context={Configs: configs},
    )
