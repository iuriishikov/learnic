from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.configs import S3Config


@dataclass(slots=True, frozen=True)
class SetUserAvatarCommand:
    user_id: UserID
    data: bytes
    content_type: str


@final
class SetUserAvatarCommandHandler:
    """Uploads a new avatar, attaches it to the user, soft-deletes the old."""

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        user_gateway: UserGateway,
        files_gateway: FilesGateway,
        file_storage: FileStorage,
        s3_config: S3Config,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._user_gateway: Final = user_gateway
        self._files_gateway: Final = files_gateway
        self._file_storage: Final = file_storage
        self._s3_config: Final = s3_config

    async def run(self, data: SetUserAvatarCommand) -> FileID:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)

        content_type = ContentType(data.content_type)
        size_bytes = FileSize(len(data.data))
        bucket = StorageBucket(self._s3_config.bucket)

        file = File.create_file(
            bucket=bucket,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_by=data.user_id,
        )

        await self._file_storage.put(
            bucket=bucket.value,
            name=file.storage_name.value,
            data=data.data,
            content_type=data.content_type,
        )
        self._entity_saver.add_one(file)
        await self._transaction.flush()

        previous_file_id = user.set_avatar(file.oid)
        if previous_file_id is not None:
            previous_file = await self._files_gateway.with_id(previous_file_id)
            if previous_file is not None and not previous_file.is_deleted:
                previous_file.mark_deleted()

        await self._transaction.commit()
        return file.oid
