import toml
from dataclasses import dataclass
import platform
import shutil
from importlib import resources
import os

@dataclass
class ConfigSection:
    def __init__(self, raw_config_section):
        for k, v in raw_config_section.items():
            if v is not None:
                setattr(self, k, v)

class Window(ConfigSection):
    width_percent:int = 20
    height_percent:int = 55
    screen_selector:int = 0
    x:int = -1
    y:int = 0

class Theme(ConfigSection):
    opacity_percent:int = 85
    background_colour:str = "#000000"
    text_colour:str = "#FFFFFF"
    font_size:int = 22
    font_style:str = "Consolas"
    future_opacity_percent:int = 50
    past_opacity_percent:int = 100

class Keybinds(ConfigSection):
    show_hide:str = "<ctrl>+<cmd>+k"

class Behaviour(ConfigSection):
    allow_dragging:bool = True
    allow_minimise:bool = False
    allow_maximise:bool = True
    allow_closing:bool = False
    snap_threshold_percent:float = 2.5

class Other(ConfigSection):
    linux_cache_location:str = "~/.cache/LyricOverlay/"
    acceptable_duration_difference:float = 1.0
    # PLACEHOLDER, must be replaced with appropriate OS cache location
    cache_location:str = "LyricOverlay"

@dataclass
class Config:
    window: Window
    theme: Theme
    keybinds: Keybinds
    behaviour: Behaviour
    other: Other
    def __init__(self, raw_config:dict):
        self.window = Window(raw_config.get("window", {}))
        self.theme = Theme(raw_config.get("theme", {}))
        self.keybinds = Keybinds(raw_config.get("keybinds", {}))
        self.behaviour = Behaviour(raw_config.get("behaviour", {}))
        self.other = Other(raw_config.get("other", {}))
        match platform.system():
            case "Linux":
                self.other.cache_location = self.other.linux_cache_location
                os.makedirs(self.other.cache_location, exist_ok=True)

def load_raw_config() -> dict[str, dict[str, str|int|float|bool]]:
    if platform.system() == "Linux":
        config_dir = os.path.expanduser("~/.config/")
        if not os.path.exists(os.path.join(config_dir, "LyricOverlay.toml")):
            with resources.files("lyric_overlay").joinpath("config.default.toml").open("rb") as src:
                os.makedirs(config_dir, exist_ok=True)  # creates .config dir if it doesn't exist
                with open(os.path.join(config_dir, "LyricOverlay.toml"), 'wb') as dst:
                    shutil.copyfileobj(src, dst)
        return toml.load(os.path.join(config_dir, "LyricOverlay.toml"))
    else:
        return {}

def load_config() -> Config:
    raw_config = load_raw_config()    
    return Config(raw_config)
