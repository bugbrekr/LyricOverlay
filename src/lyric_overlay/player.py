import dbus
import dbus.connection

class Player:
    """Handle a DBUS media player."""
    def __init__(self):
        self.bus = dbus.SessionBus()
    def _get(self, player:dbus.connection.Connection.ProxyObjectClass, key:str) -> dict|float|None:
        return player.Get(
            "org.mpris.MediaPlayer2.Player",
            key,
            dbus_interface="org.freedesktop.DBus.Properties"
        )
    def _get_playing_player(self) -> dbus.connection.Connection.ProxyObjectClass|None:
        names_list = self.bus.list_names()
        if not names_list:
            return None
        for service in names_list:
            if service.startswith("org.mpris.MediaPlayer2."):
                player = dbus.SessionBus().get_object(service, "/org/mpris/MediaPlayer2")
                status = self._get(player, "PlaybackStatus")
                if status == "Playing":
                    return player
        return None
    def get_track_info(self, player=None):
        """Fetch the track title and artist."""
        if player is None:
            player = self._get_playing_player()
            if player is None:
                return None
        metadata = self._get(player, "Metadata")
        if not metadata or not isinstance(metadata, dict):
            return None
        _artist = metadata.get("xesam:artist")
        if not isinstance(_artist, list):
            return None
        if _artist:
            artist = str(metadata["xesam:artist"][0])
        else:
            artist = ""
        duration = metadata["mpris:length"]/1000000
        return (str(metadata["xesam:title"]), artist, duration)

    def get_track_position(self, player=None) -> float|None:
        """Fetch the track playback position."""
        if player is None:
            player = self._get_playing_player()
        if player is None:
            return None
        _position = self._get(player, "Position")
        if not isinstance(_position, float) and not isinstance(_position, int):
            return None
        position = int(_position)/10e5
        return round(position, 2)