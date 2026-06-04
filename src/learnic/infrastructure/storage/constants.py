"""Tunables for the S3 object-storage adapter."""

from typing import Final

_MIB: Final = 1024 * 1024

S3_MIN_PART_SIZE_BYTES: Final = 5 * _MIB
"""S3's hard minimum size for a multipart part (all but the last).

An ``upload_part`` smaller than this is rejected with
``EntityTooSmall``, so :data:`STREAM_CHUNK_SIZE_BYTES` MUST stay at or
above this floor — otherwise multipart breaks for any payload that
spans more than one part.
"""

STREAM_CHUNK_SIZE_BYTES: Final = 8 * _MIB
"""Chunk size for streaming uploads to object storage.

The single knob for the upload memory/throughput trade-off, because
it controls two things at once:

* the size of each multipart ``upload_part`` — the bytes held in
  memory at a time while a large file streams through;
* the threshold below which a payload is buffered whole and sent in
  one ``put_object`` instead of opening a multipart upload.

Peak RAM per concurrent upload is therefore roughly this value. Raise
it to cut the number of S3 requests on large files (at the cost of
more memory per upload); lower it to shrink the footprint — but never
below :data:`S3_MIN_PART_SIZE_BYTES`.
"""
