"""Plugin registry. Add a new LED project by dropping a package in this folder
and appending its app instance to ALL_APPS — the controller discovers the rest
(views, admin routes) through the LedApp contract."""

from .ambient import AmbientApp
from .birthday import BirthdayApp
from .carousel import CarouselApp
from .clock import ClockApp
from .flights import FlightsApp
from .messages import MessagesApp
from .news import NewsApp
from .plants import PlantApp
from .reminders import ReminderApp
from .traffic import TrafficApp
from .transit import TransitApp
from .weather import WeatherApp
from .worldcup import WorldCupApp

ALL_APPS = [
    CarouselApp(),
    MessagesApp(),
    WorldCupApp(),
    WeatherApp(),
    ClockApp(),
    AmbientApp(),
    BirthdayApp(),
    PlantApp(),
    ReminderApp(),
    NewsApp(),
    FlightsApp(),
    TransitApp(),
    TrafficApp(),
]
