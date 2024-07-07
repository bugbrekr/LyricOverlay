"""
This is the main module.
It runs the application.

Author: BugBrekr
Date: 27-06-2024
"""

import threading
import time
import os
import math
import base64
import webview
import toml
from pynput import keyboard
import helpers

config = toml.load("config.toml")
KEYBINDS_SHOW_HIDE = config["keybinds"]["show_hide"]
SCREEN_SELECTOR = config["window"]["screen_selector"]

SCREEN_SIZE = webview.screens[SCREEN_SELECTOR].width, webview.screens[SCREEN_SELECTOR].height

LYRICS_CACHE_LOCATION = os.path.expanduser(config["lyrics"]["cache_location"])
os.makedirs(LYRICS_CACHE_LOCATION, exist_ok=True)

with open("content/main.html", encoding="utf-8") as f:
    HTML_CONTENT = f.read()

def _get_adjusted_window_geometry():
    sw, sh = SCREEN_SIZE
    cwp, chp = config["window"]["width_percent"], config["window"]["height_percent"]
    w, h = helpers.get_adjusted_window_geometry((sw, sh), (cwp, chp))
    return w, h

WINDOW_GEOMETRY = _get_adjusted_window_geometry()
window = webview.create_window(
    'LyricOverlay',
    html=HTML_CONTENT,
    resizable=False,
    on_top=True,
    frameless=True,
    easy_drag=config["behaviour"]["allow_dragging"],
    focus=False,
    transparent=True,
    background_color=config["theme"]["background_colour"],
    draggable=False,
    zoomable=False,
    width=WINDOW_GEOMETRY[0],
    height=WINDOW_GEOMETRY[1],
    x=SCREEN_SIZE[0]-WINDOW_GEOMETRY[0] if config["window"]["x"] == -1 else config["window"]["x"],
    y=SCREEN_SIZE[1]-WINDOW_GEOMETRY[1] if config["window"]["y"] == -1 else config["window"]["y"]
)

class Overlay:
    """This class handles the overlay window."""
    _snap_to_corner_threshold_percent = config["behaviour"]["snap_to_corner_threshold_percent"]
    SNAP_TO_CORNER_THRESHOLD = (sum(SCREEN_SIZE)/2)*_snap_to_corner_threshold_percent/100
    def __init__(self, win:webview.Window):
        self.win = win
        self.window_shown = True
        self.player = helpers.Player()
        self.lyrics_fetcher = helpers.LyricsFetcher(LYRICS_CACHE_LOCATION)
        self.status = "idle"
        threading.Thread(target=self._init_hotkey_listener).start()
    def _init_hotkey_listener(self):
        def for_canonical_l(func):
            return lambda k: func(l.canonical(k))
        hotkey = keyboard.HotKey(keyboard.HotKey.parse(KEYBINDS_SHOW_HIDE), self.on_hotkey)
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
        nwc, nec = (x,y), (x+self.win.width, y)
        swc, sec = (x, y+self.win.height), (x+self.win.width, y+self.win.height)
        if math.dist((0, 0), nwc) <= self.SNAP_TO_CORNER_THRESHOLD: # NW
            self.win.move(0, 0)
        elif math.dist((SCREEN_SIZE[0], 0), nec) <= self.SNAP_TO_CORNER_THRESHOLD: # NE
            self.win.move(SCREEN_SIZE[0]-self.win.width, 0)
        elif math.dist(SCREEN_SIZE, sec) <= self.SNAP_TO_CORNER_THRESHOLD: # SE
            self.win.move(SCREEN_SIZE[0]-self.win.width, SCREEN_SIZE[1]-self.win.height)
        elif math.dist((0, SCREEN_SIZE[1]), swc) <= self.SNAP_TO_CORNER_THRESHOLD: # SW
            self.win.move(0, SCREEN_SIZE[1]-self.win.height)
    def _apply_stylesheet(self):
        _opacity = config["theme"]["opacity"]
        _bg_rgb = helpers.hex_to_rgb(config["theme"]["background_colour"])
        background_colour = _bg_rgb+(_opacity,)
        text_colour = helpers.hex_to_rgb(config["theme"]["text_colour"])
        stylesheet = helpers.render_template(
            "content/main.css",
            background_colour=[str(i) for i in background_colour],
            text_colour=[str(i) for i in text_colour],
            font_style=config["theme"]["font_style"],
            font_size=config["theme"]["font_size"],
            past_opacity=config["theme"]["past_opacity"],
            future_opacity=config["theme"]["future_opacity"]
        )
        self.win.load_css(stylesheet)
    def init(self):
        """Window init function."""
        self.win.show()
        self._apply_stylesheet()
        self.mainloop()
    def _on_idle(self):
        print("idle")
        self.status = "idle"
        self.win.evaluate_js("clear_lyrics()")
    def _on_track_changed(self, track_info):
        print("loading:", track_info)
        self.win.evaluate_js("clear_lyrics()")
        self.status = "loading"
    def _on_lyrics_failure(self, track_info):
        print("failed:", track_info)
        self.status = "idle"
    def _on_loaded_lyrics(self, track_info, plain_lyrics):
        print("applying:", track_info)
        encoded_lrc = base64.b64encode(bytes(plain_lyrics, "utf-8")).decode()
        self.win.evaluate_js(f"populate_lyrics('{encoded_lrc}')")
        self.status = "lrc_ready"
    def _on_lyric_change(self, lyric_index):
        self.win.evaluate_js(f"highlight_lyric({lyric_index})")
    def mainloop(self):
        """Handles continuous processes."""
        prev_track_info = ()
        prev_lyric_index = (-1, 0)
        while True:
            time.sleep(0.5)
            if not self.window_shown:
                continue
            self._snap_window_to_corner()

            track_info = self.player.get_track_info()
            if track_info != prev_track_info:
                if track_info is None:
                    # Show idle notice.
                    self._on_idle()
                else:
                    self._on_track_changed(track_info)
                    # TODO: Show loading notice.
                    lyrics, res, code = self.lyrics_fetcher.fetch_synced_lyrics(
                        track_info[0],
                        track_info[1]
                    )
                    if res is True:
                        self._on_loaded_lyrics(track_info, lyrics.plain_lyrics)
                    elif code == 204:
                        # Synced lyrics not available.
                        # TODO: Add fallback to plain lyrics and show notice.
                        self._on_lyrics_failure(track_info)
                    else:
                        # Nothing is available.
                        # TODO: Show error notice.
                        self._on_lyrics_failure(track_info)
            prev_track_info = track_info
            if self.status == "lrc_ready":
                lyric_index = lyrics.get_current_lyric_index(
                    self.player.get_track_position()
                )
                if lyric_index != prev_lyric_index and lyric_index[1]:
                    self._on_lyric_change(lyric_index[0] if lyric_index[1]>=0 else -1)
                prev_lyric_index = lyric_index

overlay = Overlay(window)

class WindowEventHandler:
    """Class of all functions that handle window events."""
    def on_minimized(self):
        """Handle window minimize"""
        if not config["behaviour"]["allow_minimise"]:
            window.restore()
    def on_closing(self):
        """Handle window closing"""
        if not config["behaviour"]["allow_closing"]:
            return False

windowEventHandler = WindowEventHandler()

window.events.minimized += windowEventHandler.on_minimized
window.events.closing += windowEventHandler.on_closing
webview.start(overlay.init, gui="gtk")
