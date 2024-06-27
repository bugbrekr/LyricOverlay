import dbus
import hashlib
import os
import json
import re
from typing import Optional
import requests

class Player:
    def __init__(self):
        self.bus = dbus.SessionBus()
    def _get(self, player, key):
        return player.Get('org.mpris.MediaPlayer2.Player', key, dbus_interface='org.freedesktop.DBus.Properties')
    def _get_playing_player(self):
        for service in self.bus.list_names():
            if service.startswith('org.mpris.MediaPlayer2.'):
                player = dbus.SessionBus().get_object(service, '/org/mpris/MediaPlayer2')
                status = self._get(player, "PlaybackStatus")
                if status == "Playing":
                    return player

    def get_track_info(self, player=None):
        if player == None:
            player = self._get_playing_player()
        if player == None:
            return None
        metadata = self._get(player, "Metadata")
        return (str(metadata['xesam:title']), str(metadata['xesam:artist'][0]))

    def get_track_position(self, player=None):
        if player == None:
            player = self._get_playing_player()
        if player == None:
            return None
        position = int(self._get(player, "Position"))/10e5
        return round(position, 2)

class LyricsFetcher:
    def __init__(self, cache_folder):
        self.cache_folder = cache_folder
    def _hash_track(self, track_title, track_artist):
        return hashlib.md5((track_title+track_artist).encode()).hexdigest()
    def _get_from_cache(self, track_hash) -> dict:
        cache_location = self.cache_folder+"/lyrics/"
        if os.path.isfile(cache_location+track_hash+".json"):
            with open(cache_location+track_hash+".json") as f:
                lyrics = json.loads(f.read())
            return lyrics
        else:
            return None
    def _cache_lyrics(self, track_hash, data):
        cache_location = self.cache_folder+"/lyrics/"
        if os.path.isdir(cache_location) == False:
            os.mkdir(cache_location)
        with open(cache_location+track_hash+".json", "w") as f:
            f.write(json.dumps(data))
    def get_lrc(self, search_term: str) -> Optional[str]:
        ROOT_URL = "https://lrclib.net"
        API_ENDPOINT = ROOT_URL + "/api"
        SEARCH_ENDPOINT = API_ENDPOINT + "/search"
        url = SEARCH_ENDPOINT
        r = requests.get(
            url, 
            params={"q": search_term}, 
            headers={"User-Agent": f"LYRIC_OVERLAY v0.x (https://github.com/bugbrekr/LyricOverlay)"}
        )
        if not r.ok:
            return
        tracks = r.json()
        if not tracks:
            return
        return (tracks[0]['syncedLyrics'], tracks[0]['plainLyrics'])
    def fetch_synced(self, track_title, track_artist):
        lyrics = self._get_from_cache(self._hash_track(track_title, track_artist))
        if lyrics:
            if lyrics.get('synced_lyrics'):
                return lyrics, True
        search_term = track_title+" "+track_artist
        lrc = self.get_lrc(search_term)
        if not lrc:
            return None, False
        lyrics_data = {
            "source": "LRCLIB",
            "track_title": track_title,
            "track_artist": track_artist,
            "synced_lyrics": lrc
        }
        self._cache_lyrics(self._hash_track(track_title, track_artist), lyrics_data)
        return lyrics_data, True

class SyncedLyrics:
    def __init__(self, raw_lyrics):
        self._raw_lyrics = raw_lyrics
        self._parse_lyrics(self._raw_lyrics)
    def _extract_parts(self, raw_lyric, decimal_precision=2):
        if len(raw_lyric) == 8+decimal_precision:
            lyric = ""
        else:
            if raw_lyric[8+decimal_precision] == ' ':
                lyric = raw_lyric[9+decimal_precision:]
            else:
                lyric = raw_lyric[8+decimal_precision:]
        _timest = raw_lyric[1:7+decimal_precision]
        try:
            timest = (int(_timest[:2])*60)+float(_timest[3:])
        except ValueError:
            return False, lyric
        return round(timest, 2), lyric
    def _parse_lyrics(self, raw_lyrics):
        raw_lyrics_list = raw_lyrics.strip().split("\n")
        self.lyrics_list = []
        self.timest_list = []
        _timest = 0.0
        for raw_lyric in raw_lyrics_list:
            _r = re.findall("\[\d\d:\d\d.\d\d\]", raw_lyric)
            if _r:
                __timest, lyric = self._extract_parts(raw_lyric)
            else:
                _r = re.findall("\[\d\d:\d\d.\d\d\d\]", raw_lyric)
                if _r:
                    __timest, lyric = self._extract_parts(raw_lyric, 3)
                else:
                    self.timest_list.append(_timest)
                    self.lyrics_list.append(raw_lyric)
            if __timest == False:
                __timest = _timest
            self.timest_list.append(__timest)
            self.lyrics_list.append(lyric)
            _timest = __timest
        self.plain_lyrics = "\n".join(self.lyrics_list)

    def get_current_lyric_index(self, position):
        for i, timest in enumerate(self.timest_list):
            if position < self.timest_list[0]:
                break
            elif i == len(self.timest_list)-1:
                return i, round(position-timest, 2)
            elif position < self.timest_list[i+1]:
                return i, round(position-timest, 2)
        return 0, round(position-self.timest_list[0], 2)
    
    def get_plain_lyrics(self):
        return self.plain_lyrics