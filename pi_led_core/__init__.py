"""pi-led shared SDK: the panel sink, the 64x64 draw toolkit, the plugin
contract, the registry, and cross-process controller state. Plugins depend on
this; this depends on nothing in the project."""

from .plugin import LedApp, RenderContext, ViewSpec, make_view_key, parse_view_key
from .registry import AppRegistry
from .state import ControllerState

__all__ = [
    "LedApp",
    "RenderContext",
    "ViewSpec",
    "make_view_key",
    "parse_view_key",
    "AppRegistry",
    "ControllerState",
]
