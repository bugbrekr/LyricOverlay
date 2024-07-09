"""
This is the main module.
It runs the application.

Author: BugBrekr
Date: 27-06-2024
"""

import threading
import time
import os
import sys
import shutil
import platform
import math
import base64
import webview
import toml
from pynput import keyboard
import helpers

if getattr(sys, 'frozen', False):
    # pylint: disable=protected-access
    CWD = sys._MEIPASS
else:
    CWD = os.getcwd()

if platform.system() == "Linux":
    if not os.path.exists(os.path.expanduser("~/.config/LyricOverlay.toml")):
        print("creating config.toml")
        shutil.copyfile(
            os.path.join(CWD, "config.default.toml"),
            os.path.expanduser("~/.config/LyricOverlay.toml")
        )
    config = toml.load(os.path.expanduser("~/.config/LyricOverlay.toml"))
else:
    raise NotImplementedError(f"{platform.system()} is not supported!")
KEYBINDS_SHOW_HIDE = config["keybinds"]["show_hide"]
SCREEN_SELECTOR = config["window"]["screen_selector"]

SCREEN_SIZE = webview.screens[SCREEN_SELECTOR].width, webview.screens[SCREEN_SELECTOR].height

if platform.system() == "Linux":
    LYRICS_CACHE_LOCATION = os.path.expanduser(config["other"]["cache_location"])
else:
    raise NotImplementedError(f"{platform.system()} is not supported!")
os.makedirs(LYRICS_CACHE_LOCATION, exist_ok=True)

with open(os.path.join(CWD, "content/main.html"), encoding="utf-8") as f:
    HTML_CONTENT = f.read()

def _get_adjusted_window_geometry():
    sw, sh = SCREEN_SIZE
    cwp, chp = config["window"]["width_percent"], config["window"]["height_percent"]
    w, h = helpers.get_adjusted_window_geometry((sw, sh), (cwp, chp))
    return w, h

WINDOW_GEOMETRY = _get_adjusted_window_geometry()
window = webview.create_window(
    "LyricOverlay",
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
    SNAP_TO_HOR_EDGE_THREDHOLD = SCREEN_SIZE[0]*_snap_to_corner_threshold_percent/100
    SNAP_TO_VER_EDGE_THREDHOLD = SCREEN_SIZE[1]*_snap_to_corner_threshold_percent/100
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
        elif abs(x) <= self.SNAP_TO_HOR_EDGE_THREDHOLD: # EAST
            self.win.move(0, y)
        elif abs(SCREEN_SIZE[0]-(x+self.win.width)) <= self.SNAP_TO_HOR_EDGE_THREDHOLD: # WEST
            self.win.move(SCREEN_SIZE[0]-self.win.width, y)
        elif abs(y) <= self.SNAP_TO_VER_EDGE_THREDHOLD: # NORTH
            self.win.move(x, 0)
        elif abs(SCREEN_SIZE[1]-(y+self.win.height)) <= self.SNAP_TO_VER_EDGE_THREDHOLD: # SOUTH
            self.win.move(x, SCREEN_SIZE[1]-self.win.height)
    def _apply_stylesheet(self):
        _opacity = config["theme"]["opacity"]/100
        _bg_rgb = helpers.hex_to_rgb(config["theme"]["background_colour"])
        background_colour = _bg_rgb+(_opacity,)
        text_colour = helpers.hex_to_rgb(config["theme"]["text_colour"])
        stylesheet = helpers.render_template(
            os.path.join(CWD, "content/main.css"),
            background_colour=[str(i) for i in background_colour],
            text_colour=[str(i) for i in text_colour],
            font_style=config["theme"]["font_style"],
            font_size=config["theme"]["font_size"],
            past_opacity=config["theme"]["past_opacity"]/100,
            future_opacity=config["theme"]["future_opacity"]/100
        )
        self.win.load_css(stylesheet)
    def init(self):
        """Window init function."""
        self.win.show()
        self._apply_stylesheet()
        self.mainloop()
    def _on_idle(self):
        self.status = "idle"
        self.win.evaluate_js("clear_lyrics(); hide_notice();")
    def _on_track_changed(self):
        self._show_notice("Loading...")
        self.win.evaluate_js("clear_lyrics()")
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
                    self._on_track_changed()
                    lyrics, res, code = self.lyrics_fetcher.fetch_synced_lyrics(
                        track_info[0],
                        track_info[1]
                    )
                    if res is True:
                        self._on_lyrics_loaded(lyrics.plain_lyrics)
                    elif code == 204:
                        # Synced lyrics not available.
                        self._on_lyrics_failure(404)
                    else:
                        self._on_lyrics_failure(code)
            prev_track_info = track_info
            if self.status == "lrc_ready":
                lyric_index = lyrics.get_current_lyric_index(
                    self.player.get_track_position()
                )
                if lyric_index != prev_lyric_index and lyric_index[1]:
                    self._on_position_change(lyric_index[0] if lyric_index[1]>=0 else -1)
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
