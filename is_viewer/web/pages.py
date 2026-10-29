"""Preenche pequenos templates HTML; comportamento e estilo ficam em static/."""

from functools import cache
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import quote

from ..config import camera_topics

WEB_DIRECTORY = Path(__file__).resolve().parent


@cache
def _template(name: str) -> Template:
    return Template((WEB_DIRECTORY / "templates" / name).read_text(encoding="utf-8"))


def _render(name: str, **values: object) -> str:
    """Insere valores já escapados ou fragmentos produzidos neste módulo."""
    return _template(name).substitute(values)


def home_html() -> str:
    return _render("home.html")


def calibration_html(camera_id: int | None = None) -> str:
    selected = "" if camera_id is None else str(camera_id)
    return _render(
        "calibration.html",
        selected_camera=selected,
        overview="true" if camera_id is None else "false",
        title="Calibração das câmeras"
        if camera_id is None
        else f"Calibração · câmera {camera_id}",
    )


def dashboard_html(topics: list[str] | None = None) -> str:
    topics = camera_topics() if topics is None else topics
    cards = "\n".join(
        _render("camera_card.html", topic=escape(topic, quote=True)) for topic in topics
    )
    return _render("camera.html", cards=cards)


def mosaic_html(rows: int, columns: int) -> str:
    cells = "\n".join(_render("mosaic_cell.html") for _ in range(rows * columns))
    return _render("mosaic.html", rows=rows, columns=columns, cells=cells)


def skeleton3d_html(topic: str) -> str:
    source = "/skeleton3d-data/" + quote(topic, safe="")
    return _render(
        "world3d.html",
        topic=escape(topic, quote=True),
        source=escape(source, quote=True),
        synthetic_url=escape("/world3d-sintetico/" + quote(topic, safe=""), quote=True),
    )


def synthetic3d_html(topic: str) -> str:
    encoded = quote(topic, safe="")
    return _render(
        "world3d-synthetic.html",
        topic=escape(topic, quote=True),
        source=escape("/skeleton3d-data/" + encoded, quote=True),
        world_url=escape("/world3d/" + encoded, quote=True),
    )


def messages_html(source: str, history: int) -> str:
    return _render("messages.html", source=escape(source, quote=True), history=history)
