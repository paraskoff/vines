from pathlib import Path
from vines.config import THEME_CONFIG

STATIC_DIR = Path(__file__).parent / "static"


def generate_base_css() -> str:
    """Load CSS template and hydrate configuration theme variables."""
    css_template = (STATIC_DIR / "style.css").read_text(encoding="utf-8")

    replacements = {
        "__FONT_FAMILY__": THEME_CONFIG["font_family"],
        "__ACCENT_COLOR__": THEME_CONFIG["accent_color"],
        "__ACCENT_HOVER__": THEME_CONFIG["accent_hover"],
        "__LINK_COLOR__": THEME_CONFIG["link_color"],
        "__BG_LIGHT__": THEME_CONFIG["bg_light"],
        "__SURFACE_LIGHT__": THEME_CONFIG["surface_light"],
        "__TEXT_LIGHT__": THEME_CONFIG["text_light"],
        "__BORDER_LIGHT__": THEME_CONFIG["border_light"],
        "__BG_DARK__": THEME_CONFIG["bg_dark"],
        "__SURFACE_DARK__": THEME_CONFIG["surface_dark"],
        "__TEXT_DARK__": THEME_CONFIG["text_dark"],
        "__BORDER_DARK__": THEME_CONFIG["border_dark"],
    }

    for placeholder, val in replacements.items():
        css_template = css_template.replace(placeholder, val)

    return css_template