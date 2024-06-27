"""
This is the main module.
It runs the application.

Author: BugBrekr
Date: 27-06-2024
"""

import threading
import webview
import toml
from pynput import keyboard
import helpers

config = toml.load("config.toml")
KEYBINDS_SHOW_HIDE = config["keybinds"]["show_hide"]
SCREEN_SELECTOR = config["window"]["screen_selector"]

with open("content/main.html", encoding="utf-8") as f:
    HTML_CONTENT = f.read()

def _get_adjusted_window_geometry():
    sw, sh = webview.screens[SCREEN_SELECTOR].width, webview.screens[SCREEN_SELECTOR].height
    cwp, chp = config["window"]["width_percent"], config["window"]["height_percent"]
    w, h = helpers.get_adjusted_window_geometry((sw, sh), (cwp, chp))
    return w, h

WINDOW_GEOMETRY = _get_adjusted_window_geometry()
window = webview.create_window(
    'LyricOverlay',
    html=HTML_CONTENT,
    resizable=config["behaviour"]["allow_resizing"],
    on_top=True,
    frameless=True,
    easy_drag=config["behaviour"]["allow_dragging"],
    focus=False,
    transparent=True,
    background_color=config["theme"]["background"],
    draggable=False,
    zoomable=False,
    width = WINDOW_GEOMETRY[0],
    height = WINDOW_GEOMETRY[1]
)

class Overlay:
    """This class handles the overlay window."""
    def __init__(self, win:webview.Window):
        self.win = win
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
        print("hi")
    def _resize_to_geometry(self):
        w, h = _get_adjusted_window_geometry()
        self.win.resize(w, h)
    def _apply_stylesheet(self):
        _opacity = config["theme"]["opacity"]
        _bg_rgb = helpers.hex_to_rgb(config["theme"]["background"])
        background = _bg_rgb+(_opacity,)
        text = helpers.hex_to_rgb(config["theme"]["text"])
        stylesheet = helpers.render_template(
            "content/main.css",
            background=[str(i) for i in background],
            text=[str(i) for i in text]
        )
        self.win.load_css(stylesheet)
    def init(self):
        """Window init function."""
        self._resize_to_geometry()
        self._apply_stylesheet()

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
webview.start(overlay.init)
