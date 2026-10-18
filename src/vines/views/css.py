from pathlib import Path
from vines.themes import load_theme

STATIC_DIR = Path(__file__).parent / "static"


def generate_base_css(theme_name: str = "default") -> str:
    """Load CSS template and hydrate configuration theme variables."""
    css_template = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    theme_config = load_theme(theme_name)

    replacements = {
        "__FONT_FAMILY__": theme_config["font_family"],
        "__ACCENT_COLOR__": theme_config["accent_color"],
        "__ACCENT_HOVER__": theme_config["accent_hover"],
        "__LINK_COLOR__": theme_config["link_color"],
        "__BG_LIGHT__": theme_config["bg_light"],
        "__SURFACE_LIGHT__": theme_config["surface_light"],
        "__TEXT_LIGHT__": theme_config["text_light"],
        "__BORDER_LIGHT__": theme_config["border_light"],
        "__BG_DARK__": theme_config["bg_dark"],
        "__SURFACE_DARK__": theme_config["surface_dark"],
        "__TEXT_DARK__": theme_config["text_dark"],
        "__BORDER_DARK__": theme_config["border_dark"],
    }

    for placeholder, val in replacements.items():
        css_template = css_template.replace(placeholder, val)

    return css_template