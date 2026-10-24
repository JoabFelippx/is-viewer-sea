"""Entrada compatível com `python server.py` e `uvicorn server:app`."""

from is_viewer.app import app
from is_viewer.config import Settings

__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=Settings.from_env().port)
