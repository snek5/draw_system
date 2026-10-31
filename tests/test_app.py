from __future__ import annotations

import io
import re

import pytest

from fallback import create_app
from fallback.draw import hash_file, pick_staff, pick_winners

CSV = "\n".join(
    ["ACCTNO|ACNAME|PERDANA_FLAG|STAFF_FLAG|FINAL_CHANCES"]
    + [f"{1000 + i}|Person {i}|{'Y' if i % 3 == 0 else 'N'}|{'Y' if i % 10 == 0 else 'N'}|{i % 7 + 1}"
       for i in range(300)]
) + "\n"


@pytest.fixture()
def client():
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    with app.test_client() as c:
        c.get("/")
        yield c


def upload(client, data=CSV.encode()):
    return client.post("/upload", data={"file": (io.BytesIO(data), "entries.csv")},
                       content_type="multipart/form-data")


def setup(client, **fields):
    form = {"seed": "abc123", "perdana": "3", "mass": "4", "staff": "0", "delay": "2"}
    form.update(fields)
    return client.post("/setup", data=form)


def reveal_all(client):
    """Follow the htmx reveal chain like the browser would."""
    labels, triggers = [], []
    html = client.post("/draw/start").get_data(as_text=True)
    while True:
        match = re.search(r'hx-get="(/draw/reveal/\d+)"\s+hx-trigger="([^"]+)"', html)
        if not match:
            return labels, triggers
        triggers.append(match.group(2))
        html = client.get(match.group(1)).get_data(as_text=True)
        labels += re.findall(r'<li class="winner">(.*?)</li>', html, re.S)


def test_index_renders(client):
    page = client.get("/").get_data(as_text=True)
    assert 'hx-post="/upload"' in page
    assert "Number of Perdana Winners:" in page
    assert "htmx-2.0.4.min.js" in page


def test_upload_shows_hash_and_fills_seed(client):
    html = upload(client).get_data(as_text=True)
    assert "File Uploaded" in html
    assert hash_file(CSV.encode()) in html
    seed = re.search(r'id="seed-echo">([0-9a-f]+)<', html).group(1)
    assert 16 <= len(seed) <= 32
    assert 'hx-swap-oob="true"' in html and f'value="{seed}"' in html


def test_staff_toggle_swaps_params_and_keeps_values(client):
    html = client.get("/params?staff_draw=on&perdana=5&mass=6&delay=3").get_data(as_text=True)
    assert "Number of Staff Winners:" in html and "Perdana" not in html
    assert 'name="perdana" value="5"' in html and 'name="mass" value="6"' in html
    html = client.get("/params?perdana=5&mass=6&staff=2").get_data(as_text=True)
    assert "Number of Perdana Winners:" in html
    assert 'name="staff" value="2"' in html


def test_public_draw_end_to_end(client):
    upload(client)
    assert "draw-screen" in setup(client, show_name="on").get_data(as_text=True)
    labels, triggers = reveal_all(client)

    expected = pick_winners(CSV, 3.0, 4.0, "abc123", show_name=True, show_cert=False)
    assert labels == [w.label for w in expected.winners]
    assert len(labels) == 7
    assert triggers[0] == "load" and set(triggers[1:]) == {"load delay:2s"}

    body = client.get("/draw/download")
    assert body.headers["Content-Disposition"] == 'attachment; filename="selected_lines.csv"'
    lines = body.get_data(as_text=True).split("\n")
    assert lines[0] == "ACCTNO|ACNAME|PERDANA_FLAG|STAFF_FLAG|FINAL_CHANCES"
    assert lines[1:-1] == [w.line for w in expected.winners]
    assert lines[-1] == f"RNG Seed = abc123 | File Hash = {hash_file(CSV.encode())}"


def test_staff_draw_end_to_end(client):
    upload(client)
    setup(client, staff_draw="on", staff="5", show_cert="on", show_name="on")
    labels, _ = reveal_all(client)
    expected = pick_staff(CSV, 5.0, "abc123", show_name=True, show_cert=True)
    assert labels == [w.label for w in expected.winners]
    assert all("\n" in label for label in labels)


def test_download_has_only_revealed_winners(client):
    upload(client)
    setup(client)
    client.post("/draw/start")
    client.get("/draw/reveal/0")
    client.get("/draw/reveal/0")  # duplicate request is ignored
    client.get("/draw/reveal/1")
    lines = client.get("/draw/download").get_data(as_text=True).split("\n")
    assert len(lines) == 2 + 2


def test_second_logo_click_does_not_redraw(client):
    upload(client)
    setup(client)
    assert client.post("/draw/start").status_code == 200
    assert client.post("/draw/start").status_code == 204


def test_draw_without_file_shows_message(client):
    setup(client)
    html = client.post("/draw/start").get_data(as_text=True)
    assert "Please choose a CSV file." in html


def test_missing_column_shows_message(client):
    upload(client, b"ACCTNO|ACNAME|STAFF_FLAG|FINAL_CHANCES\n1|A|N|3\n")
    setup(client)
    html = client.post("/draw/start").get_data(as_text=True)
    assert "PERDANA_FLAG" in html


def test_too_many_winners_shows_message(client):
    upload(client)
    setup(client, perdana="500")
    html = client.post("/draw/start").get_data(as_text=True)
    assert 'class="error"' in html


def test_new_page_load_starts_fresh(client):
    upload(client)
    setup(client)
    client.post("/draw/start")
    client.get("/")
    assert client.get("/draw/download").status_code == 409


def test_labels_are_escaped(client):
    upload(client, b"ACCTNO|ACNAME|PERDANA_FLAG|STAFF_FLAG|FINAL_CHANCES\n"
                   b"2|B|N|N|5\n1|<script>x</script>|Y|N|5\n")
    setup(client, perdana="1", mass="0", show_name="on")
    labels, _ = reveal_all(client)
    assert labels == ["W1: &lt;script&gt;x&lt;/script&gt;\n"]
