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
import helpers

config = toml.load("config.toml")

with open("content/main.html", encoding="utf-8") as f:
    HTML_CONTENT = f.read()

win = webview.create_window(
    'LyricOverlay',
    html=HTML_CONTENT, on_top=True,
    frameless=True,
    easy_drag=False,
    focus=False,
    transparent=True
)

def _apply_stylesheet():
    background = helpers.hex_to_rgb(config["theme"]["background"])
    text = helpers.hex_to_rgb(config["theme"]["text"])
    stylesheet = helpers.render_template(
        "content/main.css",
        background=[str(i) for i in background],
        text=[str(i) for i in text]
    )
    win.load_css(stylesheet)

def main():
    """This is the main function."""
    time.sleep(1)
    _apply_stylesheet()
    win.move(win.x+100, win.y+10)
    print(win.dom.body)


threading.Thread(target=main).start()
webview.start()
