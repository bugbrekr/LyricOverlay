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

config = toml.load("config.toml")

with open("content/main.html", encoding="utf-8") as f:
    HTML_CONTENT = f.read()

win = webview.create_window(
    'Embedded Web View',
    html=HTML_CONTENT, on_top=True,
    frameless=True,
    easy_drag=False,
    focus=False,
    transparent=True
)


def main():
    """This is the main function."""
    time.sleep(1)
    win.move(win.x+100, win.y+10)
    print(win.dom.body)


threading.Thread(target=main).start()
webview.start()
