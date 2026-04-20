from typing import Any, Final

from aiobotocore.client import AioBaseClient
from typing_extensions import override

from learnic.application.common.storage.file_storage import FileStorage


class S3FileStorage(FileStorage):
    def __init__(self, client: AioBaseClient, bucket: str) -> None:
        self._client: Final = client
        self._bucket: Final = bucket

    @override
    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": data,
        }
        if content_type is not None:
            kwargs["ContentType"] = content_type
        await self._client.put_object(**kwargs)

    @override
    async def get(self, key: str) -> bytes | None:
        try:
            resp = await self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
        except self._client.exceptions.NoSuchKey:
            return None
        body: bytes = await resp["Body"].read()
        return body

    @override
    async def delete(self, key: str) -> None:
        await self._client.delete_object(Bucket=self._bucket, Key=key)

    @override
    async def presigned_get_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        url: str = await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
