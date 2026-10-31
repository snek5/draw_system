"""Aspirasi 6 draw system - Flask + htmx."""

from __future__ import annotations

import os
import secrets

from flask import Flask


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("FALLBACK_SECRET_KEY") or secrets.token_hex(32),
        # participant files can be large; raise via env if needed
        MAX_CONTENT_LENGTH=int(os.environ.get("FALLBACK_MAX_UPLOAD_MB", "200")) * 1024 * 1024,
    )
    if config:
        app.config.update(config)

    from .views import bp
    app.register_blueprint(bp)
    return app
