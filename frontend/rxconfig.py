"""Reflex configuration for the research console."""
import reflex as rx


class Config(rx.Config):
    pass


config = Config(
    app_name="frontend",
    frontend_path="frontend/.web",
    backend_path="frontend/.backend",
    db_url="sqlite:///frontend/.web/reflex.db",
)
