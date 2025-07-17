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
from . import helpers
from importlib import resources

if getattr(sys, 'frozen', False):
    # pylint: disable=protected-access
    CWD = sys._MEIPASS
else:
    CWD = os.getcwd()

if platform.system() == "Linux":
    config_dir = os.path.expanduser("~/.config/")
    if not os.path.exists(os.path.join(config_dir, "LyricOverlay.toml")):
        with resources.files("lyric_overlay").joinpath("config.default.toml").open() as src:
            os.makedirs(config_dir, exist_ok=True)  # Create .config dir if it doesn't exist
            with open(os.path.join(config_dir, "LyricOverlay.toml"), 'wb') as dst:
                shutil.copyfileobj(src, dst)
    config = toml.load(os.path.join(config_dir, "LyricOverlay.toml"))
else:
    raise NotImplementedError(f"{platform.system()} is not supported!")
KEYBINDS_SHOW_HIDE = config["keybinds"].get("show_hide", "<ctrl>+<cmd>+k")
SCREEN_SELECTOR = config["window"].get("screen_selector", 0)

SCREEN_SIZE = webview.screens[SCREEN_SELECTOR].width, webview.screens[SCREEN_SELECTOR].height

if platform.system() == "Linux":
    LYRICS_CACHE_LOCATION = os.path.expanduser(config["other"].get("cache_location", "~/.cache/LyricOverlay/"))
else:
    raise NotImplementedError(f"{platform.system()} is not supported!")
os.makedirs(LYRICS_CACHE_LOCATION, exist_ok=True)

ACCEPTABLE_DURATION_DIFFERENCE = config["other"].get("acceptable_duration_difference", 1)

with resources.files("lyric_overlay.content").joinpath("main.html").open(encoding="utf-8") as f:
    HTML_CONTENT = f.read()

def _get_adjusted_window_geometry():
    sw, sh = SCREEN_SIZE
    cwp, chp = config["window"].get("width_percent", 20), config["window"].get("height_percent", 55)
    w, h = helpers.get_adjusted_window_geometry((sw, sh), (cwp, chp))
    return w, h

WINDOW_GEOMETRY = _get_adjusted_window_geometry()

class Overlay:
    """This class handles the overlay window."""
    _snap_to_corner_threshold_percent = config["behaviour"].get("snap_to_corner_threshold_percent", 2.5)
    SNAP_TO_CORNER_THRESHOLD = (sum(SCREEN_SIZE)/2)*_snap_to_corner_threshold_percent/100
    SNAP_TO_HOR_EDGE_THREDHOLD = SCREEN_SIZE[0]*_snap_to_corner_threshold_percent/100
    SNAP_TO_VER_EDGE_THREDHOLD = SCREEN_SIZE[1]*_snap_to_corner_threshold_percent/100
    def __init__(self, win:webview.Window):
        self.win = win
        self.window_shown = True
        self.player = helpers.Player()
        self.lyrics_fetcher = helpers.LyricsFetcher(
            LYRICS_CACHE_LOCATION,
            ACCEPTABLE_DURATION_DIFFERENCE
        )
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
        _opacity = config["theme"].get("opacity", 85)/100
        _bg_rgb = helpers.hex_to_rgb(config["theme"].get("background_colour", "#000000"))
        background_colour = _bg_rgb+(_opacity,)
        text_colour = helpers.hex_to_rgb(config["theme"].get("text_colour", "#FFFFFF"))
        stylesheet = helpers.render_template(
            resources.files("lyric_overlay.content").joinpath("main.css"),
            background_colour=[str(i) for i in background_colour],
            text_colour=[str(i) for i in text_colour],
            font_style=config["theme"].get("font_style", "Consolas"),
            font_size=config["theme"].get("font_size", 22),
            past_opacity=config["theme"].get("past_opacity", 100)/100,
            future_opacity=config["theme"].get("future_opacity", 50)/100
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
                prev_track_info = ()
                prev_lyric_index = (-1, 0)
                self._on_idle()
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
                        track_info[1],
                        track_info[2]
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
                pos = self.player.get_track_position()
                if not pos:
                    self._show_notice("Error while accessing media player status.")
                    continue
                lyric_index = lyrics.get_current_lyric_index(
                    pos
                )
                if lyric_index != prev_lyric_index and lyric_index[1]:
                    self._on_position_change(lyric_index[0] if lyric_index[1]>=0 else -1)
                prev_lyric_index = lyric_index

class WindowEventHandler:
    """Class of all functions that handle window events."""
    def __init__(self, window):
        self.window = window
    def on_minimized(self):
        """Handle window minimize"""
        if not config["behaviour"].get("allow_minimise", False):
            self.window.restore()
    def on_closing(self):
        """Handle window closing"""
        if not config["behaviour"].get("allow_closing", False):
            return False

def main():
    window = webview.create_window(
        "LyricOverlay",
        html=HTML_CONTENT,
        resizable=False,
        on_top=True,
        frameless=True,
        easy_drag=config["behaviour"].get("allow_dragging", True),
        focus=False,
        transparent=True,
        background_color=config["theme"].get("background_colour", "#000000"),
        draggable=False,
        zoomable=False,
        width=WINDOW_GEOMETRY[0],
        height=WINDOW_GEOMETRY[1],
        x=SCREEN_SIZE[0]-WINDOW_GEOMETRY[0] if config["window"].get("x", -1) == -1 else config["window"].get("x", -1),
        y=SCREEN_SIZE[1]-WINDOW_GEOMETRY[1] if config["window"].get("y", 0) == -1 else config["window"].get("y", 0)
    )

    overlay = Overlay(window)

    windowEventHandler = WindowEventHandler(window)

    window.events.minimized += windowEventHandler.on_minimized
    window.events.closing += windowEventHandler.on_closing
    webview.start(overlay.init, gui="gtk")

# def main():
#     import pynput
#     from pynput import keyboard

#     def on_press(key):
#         print(f"Key pressed: {key}")

#     listener = keyboard.Listener(on_press=on_press)
#     listener.start()
#     listener.join()