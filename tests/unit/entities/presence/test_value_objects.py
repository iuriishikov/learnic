from learnic.entities.presence.value_objects import PresenceStatus


class TestPresenceStatus:
    def test_online_value(self) -> None:
        assert PresenceStatus.ONLINE.value == "online"

    def test_offline_value(self) -> None:
        assert PresenceStatus.OFFLINE.value == "offline"

    def test_string_compatible(self) -> None:
        # StrEnum members compare equal to their string values, which
        # the WS payload helper relies on when serializing.
        assert PresenceStatus.ONLINE == "online"
        assert PresenceStatus.OFFLINE == "offline"

    def test_round_trip_from_value(self) -> None:
        assert PresenceStatus("online") is PresenceStatus.ONLINE
        assert PresenceStatus("offline") is PresenceStatus.OFFLINE
