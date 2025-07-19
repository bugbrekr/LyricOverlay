from dataclasses import dataclass
import jinja2

@dataclass
class ScreenSize:
    width:int
    height:int
    def tuple(self):
        return (self.width, self.height)

def hex_to_rgb(h) -> tuple:
    """Convert a hex color code to an rgb tuple"""
    if h[0] == "#":
        h = h[1:]
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def render_template(path, **variables) -> str:
    """Use Jinja to render a template."""
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=[]))
    with open(path, encoding="utf-8") as f:
        content = f.read()
    template = env.from_string(content)
    return template.render(variables)