from typing import Final

from types_aiobotocore_s3 import S3Client
from types_aiobotocore_s3.type_defs import CompletedPartTypeDef
from typing_extensions import override

from learnic.application.common.storage.file_storage import (
    ByteStreamSource,
    FileStorage,
)
from learnic.infrastructure.storage.constants import STREAM_CHUNK_SIZE_BYTES


class S3FileStorage(FileStorage):
    def __init__(self, client: S3Client) -> None:
        self._client: Final = client

    @override
    async def put(
        self,
        bucket: str,
        name: str,
        data: bytes,
        content_type: str | None = None,
    ) -> None:
        if content_type is not None:
            await self._client.put_object(
                Bucket=bucket,
                Key=name,
                Body=data,
                ContentType=content_type,
            )
        else:
            await self._client.put_object(
                Bucket=bucket,
                Key=name,
                Body=data,
            )

    @override
    async def put_stream(
        self,
        bucket: str,
        name: str,
        source: ByteStreamSource,
        *,
        size: int,
        content_type: str | None = None,
    ) -> None:
        if size <= STREAM_CHUNK_SIZE_BYTES:
            body = bytearray()
            async for chunk in source.stream(STREAM_CHUNK_SIZE_BYTES):
                body.extend(chunk)
            await self.put(bucket, name, bytes(body), content_type)
            return
        await self._put_multipart(bucket, name, source, content_type)

    async def _put_multipart(
        self,
        bucket: str,
        name: str,
        source: ByteStreamSource,
        content_type: str | None,
    ) -> None:
        if content_type is not None:
            created = await self._client.create_multipart_upload(
                Bucket=bucket,
                Key=name,
                ContentType=content_type,
            )
        else:
            created = await self._client.create_multipart_upload(
                Bucket=bucket,
                Key=name,
            )
        upload_id = created["UploadId"]
        parts: list[CompletedPartTypeDef] = []
        try:
            part_number = 1
            async for chunk in source.stream(STREAM_CHUNK_SIZE_BYTES):
                if not chunk:
                    continue
                resp = await self._client.upload_part(
                    Bucket=bucket,
                    Key=name,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=chunk,
                )
                parts.append(
                    {"ETag": resp["ETag"], "PartNumber": part_number},
                )
                part_number += 1
            await self._client.complete_multipart_upload(
                Bucket=bucket,
                Key=name,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except BaseException:
            await self._client.abort_multipart_upload(
                Bucket=bucket,
                Key=name,
                UploadId=upload_id,
            )
            raise

    @override
    async def get(self, bucket: str, name: str) -> bytes | None:
        try:
            resp = await self._client.get_object(
                Bucket=bucket,
                Key=name,
            )
        except self._client.exceptions.NoSuchKey:
            return None
        body: bytes = await resp["Body"].read()
        return body

    @override
    async def delete(self, bucket: str, name: str) -> None:
        await self._client.delete_object(Bucket=bucket, Key=name)

    @override
    async def presigned_get_url(
        self,
        bucket: str,
        name: str,
        expires_in: int = 3600,
    ) -> str:
        url: str = await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": name},
            ExpiresIn=expires_in,
        )
        return url
