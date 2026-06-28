"""Plugin registry. Add a new LED project by dropping a package in this folder
and appending its app instance to ALL_APPS — the controller discovers the rest
(views, admin routes) through the LedApp contract."""

from .clock import ClockApp
from .messages import MessagesApp
from .worldcup import WorldCupApp

ALL_APPS = [
    MessagesApp(),
    WorldCupApp(),
    ClockApp(),
]
