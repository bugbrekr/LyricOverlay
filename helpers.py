"""
This is the helper module.
It contains all the functions and classes that are too
pristine to live in main.py.

Author: BugBrekr
Date: 27-06-2024
"""

import os
import json
import re
from typing import Optional
import hashlib
import dbus
import requests
import jinja2

LRCLIB_ROOT_URL = "https://lrclib.net"

class Player:
    """Handle a DBUS media player."""
    def __init__(self):
        self.bus = dbus.SessionBus()
    def _get(self, player, key):
        return player.Get(
            "org.mpris.MediaPlayer2.Player",
            key,
            dbus_interface="org.freedesktop.DBus.Properties"
        )
    def _get_playing_player(self):
        for service in self.bus.list_names():
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
        if metadata.get("xesam:artist") and len(metadata["xesam:artist"])>0:
            artist = str(metadata["xesam:artist"][0])
        else:
            artist = ""
        duration = metadata["mpris:length"]/1000000
        return (str(metadata["xesam:title"]), artist, duration)

    def get_track_position(self, player=None):
        """Fetch the track playback position."""
        if player is None:
            player = self._get_playing_player()
        if player is None:
            return
        position = int(self._get(player, "Position"))/10e5
        return round(position, 2)

class LyricsFetcher:
    """Fetch lyrics from LRCLIB and handle caching of returned lyrics."""
    def __init__(self, cache_folder, acceptable_duration_difference):
        self.cache_folder = cache_folder
        self.acceptable_duration_difference = acceptable_duration_difference
    def _hash_track(self, track_title, track_artist, duration):
        return hashlib.md5((track_title+track_artist+str(duration)).encode()).hexdigest()
    def _get_from_cache(self, track_hash) -> dict:
        cache_location = self.cache_folder+"/lyrics/"
        if os.path.isfile(cache_location+track_hash+".json"):
            with open(cache_location+track_hash+".json", encoding="utf-8") as f:
                lyrics = json.loads(f.read())
            return lyrics
        else:
            return None
    def _cache_lyrics(self, track_hash, data):
        cache_location = self.cache_folder+"/lyrics/"
        if os.path.isdir(cache_location) is False:
            os.mkdir(cache_location)
        with open(cache_location+track_hash+".json", "w", encoding="utf-8") as f:
            f.write(json.dumps(data))
    def _remove_from_cache(self, track_hash):
        cache_location = self.cache_folder+"/lyrics/"
        if os.path.isdir(cache_location) is False:
            os.mkdir(cache_location)
            return
        os.remove(cache_location+track_hash+".json")
    def _get_lrc(self, search_term: str, duration):
        """
        synced_lyrics, plain_lyrics, is_instrumental, success, status_code
        """
        try:
            r = requests.get(
            LRCLIB_ROOT_URL+"/api/search",
            params={"q": search_term},
            headers={"User-Agent": "LYRIC_OVERLAY v0.x (https://github.com/bugbrekr/LyricOverlay)"},
            timeout=3 # seconds
        )
        except requests.exceptions.Timeout:
            print("[CRITICAL]: Request timed out.")
            return None, None, None, False, 408
        except requests.exceptions.RequestException as e:
            print("[CRITICAL]:", e)
            return None, None, None, False, 400
        if not r.ok:
            print("[CRITICAL]: {r.ok}, {r.text}")
            return None, None, None, False, 500
        tracks = r.json()
        if not tracks:
            return None, None, None, False, 404
        track = None
        for track in tracks:
            if abs(track["duration"]-duration) <= self.acceptable_duration_difference:
                break
        if not track:
            return None, None, None, False, 404
        return (
            track.get("syncedLyrics"),
            track.get("plainLyrics"),
            track["instrumental"],
            True,
            200
        )
    def fetch_lrc(self, track_title, track_artist, duration:int):
        """Fetch synced lyrics data for a track."""
        _track_hash = self._hash_track(track_title, track_artist, duration)
        lyrics = self._get_from_cache(_track_hash)
        if lyrics:
            if lyrics.get("instrumental") is True:
                return lyrics, True, 204
            elif lyrics.get("synced_lyrics") is not None:
                return lyrics, True, 200
            elif lyrics.get("synced_lyrics") is None:
                self._remove_from_cache(_track_hash) # bad cache
        search_term = track_title+" "+track_artist
        lrc, plrc, instrumental, res, code = self._get_lrc(search_term, duration)
        if not res:
            return None, False, code
        lyrics_data = {
            "source": "LRCLIB",
            "track_title": track_title,
            "track_artist": track_artist,
            "instrumental": instrumental,
            "synced_lyrics": lrc,
            "plain_lyrics": plrc
        }
        if instrumental:
            self._cache_lyrics(_track_hash, lyrics_data)
            return lyrics_data, True, 204
        elif lrc is not None:
            self._cache_lyrics(_track_hash, lyrics_data)
            return lyrics_data, True, 200
        elif lrc is None and plrc is not None:
            # don't cache. synced lyrics could be available later.
            return lyrics_data, True, 206
    def fetch_synced_lyrics(self, track_title, track_artist, duration:int):
        """
        Get synced lyrics object for a track.
        Returned status codes:
            200 - Synced lyrics fetched (plain lyrics possibly unavailable)
            206 - Only plain lyrics fetched
            204 - No lyrics available (instrumental)
            404 - No lyrics found
            408 - Request timed out (no lyrics)
            400 - Requests Error (critical) (obviously no lyrics)
            500 - Server returned non-200 response (no lyrics)
        """
        lrc, res, code = self.fetch_lrc(track_title, track_artist, duration)
        if not res:
            return None, False, code
        if code == 206:
            return lrc["plain_lyrics"], False, 206
        elif code == 204:
            return None, False, 206
        return SyncedLyrics(
            lrc["synced_lyrics"],
            lrc["track_title"],
            lrc["track_artist"],
        ), True, 200

class SyncedLyrics:
    """Encapsulate the synced lyrics data in a nice class to use cool functions."""
    def __init__(self, raw_lyrics, track_title, track_artist):
        self._raw_lyrics = raw_lyrics
        self.track_title = track_title
        self.track_artist = track_artist
        self._parse_lyrics(self._raw_lyrics)
    def _extract_parts(self, raw_lyric, decimal_precision=2): # i forgot what this does
        if len(raw_lyric) == 8+decimal_precision:
            lyric = ""
        else:
            if raw_lyric[8+decimal_precision] == " ":
                lyric = raw_lyric[9+decimal_precision:]
            else:
                lyric = raw_lyric[8+decimal_precision:]
        _timest = raw_lyric[1:7+decimal_precision]
        try:
            timest = (int(_timest[:2])*60)+float(_timest[3:])
        except ValueError:
            return False, lyric
        return round(timest, 2), lyric
    def _parse_lyrics(self, raw_lyrics): # i forgot how this does
        raw_lyrics_list = raw_lyrics.strip().split("\n")
        self.lyrics_list = []
        self.timest_list = []
        _timest = 0.0
        for raw_lyric in raw_lyrics_list:
            _r = re.findall(r"\[\d\d:\d\d.\d\d\]", raw_lyric)
            if _r:
                __timest, lyric = self._extract_parts(raw_lyric)
            else:
                _r = re.findall(r"\[\d\d:\d\d.\d\d\d\]", raw_lyric)
                if _r:
                    __timest, lyric = self._extract_parts(raw_lyric, 3)
                else:
                    self.timest_list.append(_timest)
                    self.lyrics_list.append(raw_lyric)
            if __timest is False:
                __timest = _timest
            self.timest_list.append(__timest)
            self.lyrics_list.append(lyric)
            _timest = __timest
        self.plain_lyrics = "\n".join(self.lyrics_list)
    def get_current_lyric_index(self, position):
        """
        Return the index for the currently playing lyric and
        the duration passed since the lyric.
        """
        for i, timest in enumerate(self.timest_list):
            if position < self.timest_list[0]:
                break
            elif i == len(self.timest_list)-1:
                return i, round(position-timest, 2)
            elif position < self.timest_list[i+1]:
                return i, round(position-timest, 2)
        return 0, round(position-self.timest_list[0], 2)
    def get_lyric(self, index:int):
        """Get selected line from lyrics with index."""
        if index > len(self.lyrics_list)-1:
            return None
        return self.lyrics_list[index]

def hex_to_rgb(h) -> tuple:
    """Convert a hex color code to an rgb tuple"""
    if h[0] == "#":
        h = h[1:]
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def render_template(path, **variables) -> str:
    """Use Jinja to render a template."""
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=[]))
    with open(path, encoding="utf-8") as f:
        content = f.read()
    template = env.from_string(content)
    return template.render(variables)

def get_adjusted_window_geometry(screen_size, size_percent):
    """Get adjusted window geometry."""
    w = screen_size[0]*size_percent[0]/100
    h = screen_size[1]*size_percent[1]/100
    return int(w), int(h)
