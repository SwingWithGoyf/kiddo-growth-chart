"""Flask blueprint, plus a standalone app for people who just want to run it.

A blueprint so an existing site can mount it at a path it already serves, with
no new port and no new firewall grant::

    from kiddo_growth_chart.web import blueprint
    app.register_blueprint(blueprint(config), url_prefix="/heights")

Images are proxied, never linked, so a provider's credential stays in this
process rather than reaching every device that renders the page.
"""

from __future__ import annotations

import datetime as dt

from flask import Blueprint, Flask, abort, jsonify, render_template, request

from ..config import Config
from ..loader import DatasetError, load
from ..model import CM_PER_INCH
from ..projections import Clock, frames, project
from ..providers import registry


def _payload(dataset, clock: Clock) -> dict:
    proj = project(dataset, clock)
    kid_meta = {k.key: k for k in dataset}
    return {
        "clock": proj.clock.value,
        "x": {"min": proj.x_min, "max": proj.x_max},
        "cm": {"min": proj.cm_min, "max": proj.cm_max},
        "series": [
            {
                "key": s.kid_key,
                "name": s.name,
                "dob": kid_meta[s.kid_key].dob.isoformat(),
                "mixed_methods": kid_meta[s.kid_key].mixed_methods,
                "points": [
                    {
                        "x": p.x,
                        "cm": p.cm,
                        "in": round(p.cm / CM_PER_INCH, 1),
                        "date": p.date.isoformat(),
                        "age_days": p.age_days,
                        "age_years": round(p.age_years, 2),
                        "method": p.method,
                        "label_x": p.label_x,
                    }
                    for p in s.points
                ],
                "segments": [
                    {"a": sg.a.x, "b": sg.b.x, "mixed_method": sg.mixed_method}
                    for sg in s.segments
                ],
            }
            for s in proj.series
        ],
        "frames": [
            {
                "index": f.index,
                "label": f.label,
                "x": f.x,
                "heights": f.heights,
                "grew": list(f.grew),
                "dates": {k: v.isoformat() for k, v in f.dates.items()},
            }
            for f in frames(dataset, clock)
        ],
    }


def blueprint(config: Config | None = None) -> Blueprint:
    config = config or Config()
    bp = Blueprint(
        "kiddo_growth_chart",
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static/kiddo-growth-chart",
    )

    def provider():
        return registry.get(config.provider, **config.provider_options)

    @bp.route("/")
    def index():
        try:
            dataset = load(config.dataset)
        except DatasetError as exc:
            # An empty chart and a broken config must not look the same, or a
            # dead widget survives on a wall for a week.
            return render_template("error.html", message=str(exc)), 500
        return render_template(
            "chart.html",
            config=config,
            kids=list(dataset),
            generated=dt.datetime.now().isoformat(timespec="seconds"),
        )

    @bp.route("/data.json")
    def data():
        clock = Clock(request.args.get("clock", "date"))
        try:
            dataset = load(config.dataset)
        except DatasetError as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify(_payload(dataset, clock))

    @bp.route("/photo/<kid_key>/<int:year>")
    def photo(kid_key: str, year: int):
        """One photo of this kid taken in this calendar year, or 404.

        404 is a real answer; the caller draws the datapoint without a portrait
        rather than reaching for a photo from the wrong age.
        """
        try:
            dataset = load(config.dataset)
            kid = dataset.by_key(kid_key)
        except (DatasetError, KeyError):
            abort(404)
        if not kid.photo_person_id:
            abort(404)
        p = provider()
        found = p.photo_for(
            kid.photo_person_id,
            dt.date(year, 1, 1),
            dt.date(year, 12, 31),
            prefer_full_body=request.args.get("body") == "1",
        )
        if not found:
            abort(404)
        try:
            data_bytes, ctype = p.image_bytes(found.id)
        except (FileNotFoundError, NotImplementedError):
            abort(404)
        headers = {
            "Cache-Control": "private, max-age=3600",
            "X-Photo-Taken": found.taken.isoformat(),
        }
        if found.face:
            box = found.face.clamped()
            headers["X-Face-Box"] = f"{box.x},{box.y},{box.w},{box.h}"
        return data_bytes, 200, {"Content-Type": ctype, **headers}

    @bp.route("/providers.json")
    def providers():
        """What sources are installed, and what identities the active one knows.

        Data for the binding screen: kid -> person is a decision a human makes
        once, against the names the source reports rather than a guess.
        """
        p = provider()
        return jsonify(
            {
                "active": config.provider,
                "installed": sorted(registry.available()),
                "people": [
                    {"id": x.id, "name": x.name, "photo_count": x.photo_count}
                    for x in p.people()
                ],
            }
        )

    return bp


def create_app(config: Config | None = None) -> Flask:
    app = Flask(__name__)
    app.register_blueprint(blueprint(config or Config.load()))
    return app
