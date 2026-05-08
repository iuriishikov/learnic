import uuid
from datetime import datetime, timezone

from learnic.entities.presence.models import Presence
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID


class TestPresence:
    def test_uses_user_id_as_oid(self) -> None:
        user_id = UserID(uuid.uuid4())
        now = datetime.now(timezone.utc)

        presence = Presence(
            oid=user_id,
            status=PresenceStatus.ONLINE,
            last_seen_at=now,
        )

        assert presence.oid == user_id
        assert presence.status is PresenceStatus.ONLINE
        assert presence.last_seen_at == now
