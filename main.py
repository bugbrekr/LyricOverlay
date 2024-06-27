"""
This is the main module.
It runs the application.

Author: BugBrekr
Date: 27-06-2024
"""

import threading
import time
import webview
import toml
from pynput import keyboard
import helpers

config = toml.load("config.toml")
KEYBINDS_SHOW_HIDE = config["keybinds"]["show_hide"]
SCREEN_SELECTOR = config["window"]["screen_selector"]

SCREEN_SIZE = webview.screens[SCREEN_SELECTOR].width, webview.screens[SCREEN_SELECTOR].height

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
        self.window_shown = True
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
    def _keep_window_in_screen(self):
        x, y = self.win.x, self.win.y
        if x+self.win.width > SCREEN_SIZE[0]:
            x = SCREEN_SIZE[0]-self.win.width
        elif x < 0:
            x = 0
        if y+self.win.height > SCREEN_SIZE[1]:
            y = SCREEN_SIZE[1]-self.win.height
        elif y < 0:
            y = 0
        self.win.move(x, y)
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
        self.win.show()
        self._apply_stylesheet()
        self.mainloop()
    def mainloop(self):
        """Handles continuous processes."""
        while True:
            time.sleep(0.5)
            self._keep_window_in_screen()

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
