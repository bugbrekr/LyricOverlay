from dbus_next.aio import MessageBus
from dbus_next import Variant
import asyncio
from functools import wraps

def run_async(func):
    """Decorator to run async functions synchronously"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(func(*args, **kwargs))
    return wrapper

class Player:
    async def _get_playing_player(self):
        bus = await MessageBus().connect()
        introspect = await bus.introspect('org.freedesktop.DBus', '/org/freedesktop/DBus')
        proxy = bus.get_proxy_object('org.freedesktop.DBus', '/org/freedesktop/DBus', introspect)
        dbus_iface = proxy.get_interface('org.freedesktop.DBus')
        names = await dbus_iface.call_list_names()
        for name in names:
            if name.startswith('org.mpris.MediaPlayer2.'):
                player_introspect = await bus.introspect(name, '/org/mpris/MediaPlayer2')
                player_obj = bus.get_proxy_object(name, '/org/mpris/MediaPlayer2', player_introspect)
                props_iface = player_obj.get_interface('org.freedesktop.DBus.Properties')
                playback_status = await props_iface.call_get('org.mpris.MediaPlayer2.Player', 'PlaybackStatus')
                if playback_status.value == "Playing":
                    return player_obj
        return None
    @run_async
    async def get_track_info(self):
        player = await self._get_playing_player()
        if player is None:
            return None
        props_iface = player.get_interface('org.freedesktop.DBus.Properties')
        metadata = await props_iface.call_get('org.mpris.MediaPlayer2.Player', 'Metadata')
        metadata = metadata.value
        _title = metadata.get("xesam:title")
        if isinstance(_title, Variant) and isinstance(_title.value, str):
            title = _title.value
        else:
            return None
        _artist = metadata.get("xesam:artist")
        if isinstance(_artist, Variant) and isinstance(_artist.value, list):
            artist = _artist.value[0]
        else:
            return None
        _duration = metadata.get("mpris:length")
        if isinstance(_duration, Variant) and isinstance(_duration.value, int):
            duration = round(_duration.value/1000000, 2)
        return title, artist, duration
    @run_async
    async def get_track_position(self):
        player = await self._get_playing_player()
        if player is None:
            return None
        player_iface = player.get_interface('org.mpris.MediaPlayer2.Player')
        pos = await player_iface.get_position()
        return round(pos/1000000, 2)
