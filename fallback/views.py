from __future__ import annotations

from flask import (Blueprint, Response, abort, render_template, request,
                   session)

from .draw import (DrawError, decode_csv, hash_file, new_seed, pick_staff,
                   pick_winners, results_csv)
from .jscompat import parse_int
from .state import store

bp = Blueprint("draw", __name__)


def _state():
    state = store.get(session.get("sid"))
    if state is None:
        abort(409, "This draw session has expired. Reload the page to start again.")
    return state


def _flag(name: str) -> bool:
    return request.form.get(name) == "on"


@bp.get("/")
def index():
    # A page load starts a fresh draw, like reloading the old single-page app.
    store.drop(session.get("sid"))
    sid, _ = store.new()
    session["sid"] = sid
    return render_template("index.html")


@bp.post("/upload")
def upload():
    state = _state()
    file = request.files.get("file")
    if file is None or not file.filename:
        return render_template("partials/file_input.html", error="Please choose a CSV file.")
    data = file.read()
    state.file_bytes = data
    state.file_hash = hash_file(data)
    state.seed = new_seed()
    return render_template("partials/file_status.html",
                           file_hash=state.file_hash, seed=state.seed)


@bp.get("/params")
def params():
    staff = request.args.get("staff_draw") == "on"
    return render_template("partials/params.html", staff_draw=staff)


@bp.post("/setup")
def setup():
    """Submit: capture the settings and switch to the draw screen.
    Like the original, nothing is validated until the draw starts."""
    state = _state()
    form = request.form
    state.seed = form.get("seed", "")
    state.staff_draw = _flag("staff_draw")
    state.show_cert = _flag("show_cert")
    state.show_name = _flag("show_name")
    state.vip = parse_int(form.get("vip", ""))
    state.mass = parse_int(form.get("mass", ""))
    state.staff = parse_int(form.get("staff", ""))
    state.delay = parse_int(form.get("delay", ""))
    state.submitted = True
    return render_template("partials/draw_screen.html")


@bp.post("/draw/start")
def start():
    """Logo click: run the draw and start revealing winners."""
    state = _state()
    if not state.submitted:
        abort(409)
    if state.result is not None:
        return "", 204  # already drawn; the reveal is under way
    if state.file_bytes is None:
        return render_template("partials/draw_error.html", message="Please choose a CSV file.")

    content = decode_csv(state.file_bytes)
    try:
        if state.staff_draw:
            result = pick_staff(content, state.staff, state.seed,
                                state.show_name, state.show_cert)
        else:
            result = pick_winners(content, state.vip, state.mass, state.seed,
                                  state.show_name, state.show_cert)
    except DrawError as exc:
        return render_template("partials/draw_error.html", message=str(exc))

    state.result = result
    return render_template("partials/results.html", next_index=0,
                           has_next=bool(result.winners), delay=0)


@bp.get("/draw/reveal/<int:index>")
def reveal(index: int):
    """Show winner ``index`` and schedule the next one after the delay."""
    state = _state()
    result = state.result
    if result is None or not 0 <= index < len(result.winners):
        abort(404)
    winner = result.winners[index]
    if index == state.revealed:  # ignore duplicate/out-of-order requests
        state.revealed += 1
        state.picked_lines.append(winner.line)
    delay = state.delay if state.delay == state.delay and state.delay > 0 else 0
    return render_template("partials/winner.html", winner=winner,
                           next_index=index + 1,
                           has_next=index + 1 < len(result.winners),
                           delay=int(delay))


@bp.get("/draw/download")
def download():
    """Spacebar: the winners revealed so far, with seed and file hash."""
    state = _state()
    if state.result is None:
        abort(409)
    body = results_csv(state.result.headers, state.picked_lines,
                       state.seed, state.file_hash)
    return Response(body, mimetype="text/plain", headers={
        "Content-Disposition": 'attachment; filename="selected_lines.csv"',
    })


@bp.app_errorhandler(409)
def expired(err):
    return Response(err.description or "Conflict", status=409, mimetype="text/plain")
