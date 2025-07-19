import jinja2
import webview
from . import config as config_helper
from . import commons
from .overlay import Overlay
from importlib import resources

def get_window_geometry(screen_size, size_percent):
    """Get adjusted window geometry."""
    w = screen_size[0]*size_percent[0]/100
    h = screen_size[1]*size_percent[1]/100
    return int(w), int(h)

def get_adjusted_window_geometry(screen_size:commons.ScreenSize, window_config:config_helper.Window):
    cwp, chp = window_config.width_percent, window_config.height_percent
    w, h = get_window_geometry((screen_size.width, screen_size.height), (cwp, chp))
    return w, h

class WindowEventHandler:
    """Window event handlers"""
    def __init__(self, window, behaviour_config:config_helper.Behaviour):
        self.window = window
        self.behaviour_config = behaviour_config
    def on_minimized(self):
        """Handle window minimize"""
        if not self.behaviour_config.allow_minimise:
            self.window.restore()
    def on_closing(self):
        """Handle window closing"""
        if not self.behaviour_config.allow_closing:
            return False

class Window:
    def __init__(self, config:config_helper.Config):
        self.config = config
        self.overlay = self._build_window()
    def _build_window(self):
        screen_size = commons.ScreenSize(
            webview.screens[self.config.window.screen_selector].width,
            webview.screens[self.config.window.screen_selector].height
        )
        window_geometry = get_adjusted_window_geometry(screen_size, self.config.window)
        with resources.files("lyric_overlay.content").joinpath("main.html").open(encoding="utf-8") as f:
            HTML_CONTENT = f.read()
        self.window = webview.create_window(
            "LyricOverlay",
            html=HTML_CONTENT,
            resizable=False,
            on_top=True,
            frameless=True,
            easy_drag=self.config.behaviour.allow_dragging,
            focus=False,
            transparent=True,
            background_color=self.config.theme.background_colour,
            draggable=False,
            zoomable=False,
            width=window_geometry[0],
            height=window_geometry[1],
            x=screen_size.width-window_geometry[0] if self.config.window.x == -1 else self.config.window.x,
            y=screen_size.height-window_geometry[1] if self.config.window.y == -1 else self.config.window.y
        )

        windowEventHandler = WindowEventHandler(self.window, self.config.behaviour)
        self.window.events.minimized += windowEventHandler.on_minimized
        self.window.events.closing += windowEventHandler.on_closing  
        return Overlay(self.window, self.config, screen_size)
    def start(self):
        webview.start(self.overlay.init, gui="gtk")
