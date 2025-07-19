"""
This is the main module.
It runs the application.

Author: BugBrekr
Date: 27-06-2024
"""

import os
import platform
import webview
from importlib import resources
from . import config as config_helper
from . import gui

SUPPORTED_PLATFORMS = (
    "Linux",
)
if platform.system() not in SUPPORTED_PLATFORMS:
    raise NotImplementedError(f"{platform.system()} is not yet supported!")

config = config_helper.load_config()

def main():
    window = gui.Window(config)
    window.start()
