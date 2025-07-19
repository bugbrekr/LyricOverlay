import webview
from pynput import keyboard, mouse
import math
from importlib import resources
import time
import threading
import base64
from . import config as config_helper
from . import player as player_helper
from . import lyrics as lyrics_helper
from . import commons

class Overlay:
    """Overlay window"""
    def __init__(self, win:webview.Window, config:config_helper.Config, screen_size:commons.ScreenSize):
        self.win = win
        self.config = config
        self.screen_size = screen_size
        self.SNAP_TO_HOR_EDGE_THREDHOLD = screen_size.width*config.behaviour.snap_threshold_percent/100
        self.SNAP_TO_VER_EDGE_THREDHOLD = screen_size.height*config.behaviour.snap_threshold_percent/100
        self.window_shown = True
        self.player = player_helper.Player()
        self.lyrics_fetcher = lyrics_helper.LyricsFetcher(
            self.config.other.cache_location,
            self.config.other.acceptable_duration_difference
        )
        self.status = "idle"
        self.mouse_held = False
        self.mouse_listener = mouse.Listener(
            on_click=self._on_click
        )
        self.mouse_listener.start()
        threading.Thread(target=self._init_hotkey_listener).start()
    def _on_click(self, x, y, button, pressed):
        """Track left mouse button state"""
        if button == mouse.Button.left:
            self.mouse_held = pressed
            if not pressed and commons.check_point_in_rect(
                (x, y),
                (
                    (self.win.x, self.win.y),
                    (self.win.x+self.win.width, self.win.y+self.win.height)
                )
            ):
                self._snap_window_to_corner()
    def _init_hotkey_listener(self):
        def for_canonical_l(func):
            return lambda k: func(l.canonical(k))
        hotkey = keyboard.HotKey(keyboard.HotKey.parse(self.config.keybinds.show_hide), self.on_hotkey)
        l = keyboard.Listener(
            on_press=for_canonical_l(hotkey.press),
            on_release=for_canonical_l(hotkey.release)
        )
        l.start()
    def on_hotkey(self):
        """Show/hide the window when the hotkey is pressed."""
        if self.window_shown:
            self.win.hide()
        else:
            self.win.show()
        self.window_shown = not self.window_shown
    def _snap_window_to_corner(self):
        x, y = self.win.x, self.win.y
        wc = abs(x) <= self.SNAP_TO_HOR_EDGE_THREDHOLD
        ec = abs(self.screen_size.width-(x+self.win.width)) <= self.SNAP_TO_HOR_EDGE_THREDHOLD
        nc = abs(y) <= self.SNAP_TO_VER_EDGE_THREDHOLD
        sc = abs(self.screen_size.height-(y+self.win.height)) <= self.SNAP_TO_VER_EDGE_THREDHOLD
        if nc and wc: # NW
            self.win.move(0, 0)
        elif nc and ec: # NE
            self.win.move(self.screen_size.width-self.win.width, 0)
        elif sc and ec: # SE
            self.win.move(self.screen_size.width-self.win.width, self.screen_size.height-self.win.height)
        elif sc and wc: # SW
            self.win.move(0, self.screen_size.height-self.win.height)
        elif wc: # WEST
            self.win.move(0, y)
        elif ec: # EAST
            self.win.move(self.screen_size.width-self.win.width, y)
        elif nc: # NORTH
            self.win.move(x, 0)
        elif sc: # SOUTH
            self.win.move(x, self.screen_size.height-self.win.height)
    def _apply_stylesheet(self):
        _opacity = self.config.theme.opacity_percent/100
        _bg_rgb = commons.hex_to_rgb(self.config.theme.background_colour)
        background_colour = _bg_rgb+(_opacity,)
        text_colour = commons.hex_to_rgb(self.config.theme.text_colour)
        stylesheet = commons.render_template(
            resources.files("lyric_overlay.content").joinpath("main.css"),
            background_colour=[str(i) for i in background_colour],
            text_colour=[str(i) for i in text_colour],
            font_style=self.config.theme.font_style,
            font_size=self.config.theme.font_size,
            past_opacity=self.config.theme.past_opacity_percent/100,
            future_opacity=self.config.theme.future_opacity_percent/100
        )
        self.win.load_css(stylesheet)
    def init(self):
        """Window init function."""
        self.win.show()
        self._apply_stylesheet()
        self.mainloop()
    def _hide_notice(self):
        self.win.evaluate_js("hide_notice();")
    def _on_idle(self):
        self.status = "idle"
        self.win.evaluate_js("clear_lyrics(); hide_notice();")
    def _on_track_changed(self):
        self.win.evaluate_js("clear_lyrics()")
        self._show_notice("Loading...")
        self.status = "loading"
    def _on_lyrics_failure(self, code):
        self.status = "idle"
        if code == 404:
            self._show_notice("Sorry, lyrics are unavailable for this track.")
        elif code == 206:
            self._show_notice("No lyrics exist for this track.")
        elif code == 408:
            self._show_notice("Error: Request timed out.")
        elif code == 400:
            self._show_notice("ERROR: An unkown error has occurred.")
        elif code == 500:
            self._show_notice("Error: LRCLIB has returned a non-200 response.")
    def _on_lyrics_loaded(self, plain_lyrics):
        encoded_lrc = base64.b64encode(bytes(plain_lyrics, "utf-8")).decode()
        self.win.evaluate_js(f"populate_lyrics(\"{encoded_lrc}\")")
        self.status = "lrc_ready"
    def _on_position_change(self, lyric_index):
        self.win.evaluate_js(f"highlight_lyric({lyric_index})")
    def _show_notice(self, notice):
        self.win.evaluate_js(f"show_notice(\"{notice}\")")
    def mainloop(self):
        """Handles continuous processes."""
        prev_track_info = ()
        prev_lyric_index = (-1, 0)
        lyrics = lyrics_helper.SyncedLyrics("", "", "")
        while True:
            time.sleep(0.5)
            if not self.window_shown:
                prev_track_info = ()
                prev_lyric_index = (-1, 0)
                self._on_idle()
                continue

            track_info = self.player.get_track_info()
            if track_info != prev_track_info:
                if track_info is None:
                    # Show idle notice.
                    self._on_idle()
                    continue
                else:
                    self._on_track_changed()
                    lyrics, code = self.lyrics_fetcher.fetch_synced_lyrics(
                        track_info[0],
                        track_info[1],
                        track_info[2]
                    )
                    if isinstance(lyrics, lyrics_helper.SyncedLyrics):
                        self._on_lyrics_loaded(lyrics.plain_lyrics)
                    elif code == 204:
                        # Synced lyrics not available.
                        self._on_lyrics_failure(404)
                    else:
                        self._on_lyrics_failure(code)
            prev_track_info = track_info
            if self.status == "lrc_ready":
                pos = self.player.get_track_position()
                if not pos:
                    self._show_notice("An error occurred while accessing media player status.")
                    continue
                lyric_index = lyrics.get_current_lyric_index( # type: ignore it's handled by self.status
                    pos
                )
                if lyric_index != prev_lyric_index and lyric_index[1]:
                    self._on_position_change(lyric_index[0] if lyric_index[1]>=0 else -1)
                prev_lyric_index = lyric_index
