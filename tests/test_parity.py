"""Parity tests: the Python draw must match the original React app exactly.

The reference is the original ``helpers.js`` from the React app
(tests/parity/reference/helpers.js, unmodified), executed in Node with the
same seedrandom / crypto-js versions. Needs ``node`` and
``npm ci --prefix tests/parity``; skipped otherwise.
"""

from __future__ import annotations

import base64
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from fallback.draw import DrawError, hash_file, pick_staff, pick_winners, results_csv
from fallback.jscompat import SeedRandom, parse_int, v8_sort

PARITY_DIR = Path(__file__).parent / "parity"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not (PARITY_DIR / "node_modules" / "seedrandom").exists(),
    reason="needs node and `npm ci --prefix tests/parity`",
)


def run_reference(cases):
    proc = subprocess.run(
        ["node", "run_reference.mjs"],
        cwd=PARITY_DIR,
        input=json.dumps({"cases": cases}),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)["results"]


# --------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------

SEEDS = [
    "", "a", "abc", "hello world", "0", "f3a91c0e7d2b5", "8a1f0c3e9b7d2a4f6e1c0b9d8a7f6e5d",
    "ünïcödé ✓", "emoji 🎲 seed", "x" * 255, "y" * 256, "z" * 257, "long " * 120,
]


def test_seedrandom_matches():
    cases = [{"kind": "rng", "seed": s, "n": 200} for s in SEEDS]
    for case, ref in zip(cases, run_reference(cases)):
        rng = SeedRandom(case["seed"])
        assert [rng() for _ in range(case["n"])] == ref["values"], case["seed"]


@pytest.mark.parametrize("n", [0, 1, 2, 3, 5, 10, 31, 32, 33, 63, 64, 65, 100, 127, 128,
                               129, 200, 257, 500, 1000, 2048, 5000])
def test_v8_sort_matches(n):
    cases = [{"kind": "sort", "seed": f"sort-{n}-{k}", "n": n} for k in range(8)]
    for case, ref in zip(cases, run_reference(cases)):
        rng = SeedRandom(case["seed"])
        calls = 0

        def cmp(a, b):
            nonlocal calls
            calls += 1
            return rng() - 0.5

        order = v8_sort(list(range(n)), cmp)
        assert order == ref["order"]
        assert calls == ref["calls"]
        assert rng() == ref["next"]


def test_hash_matches():
    blobs = [b"", b"abc", "ACCTNO|ACNAME\n1|Ali\n".encode(), bytes(range(256)) * 50]
    cases = [{"kind": "hash", "base64": base64.b64encode(b).decode()} for b in blobs]
    for blob, ref in zip(blobs, run_reference(cases)):
        assert hash_file(blob) == ref["hashed"]
        assert 16 <= len(ref["seed"]) <= 32


# --------------------------------------------------------------------------
# Whole draws on generated files
# --------------------------------------------------------------------------

def _chance(r: random.Random) -> str:
    return r.choice([
        str(r.randint(1, 20)), str(r.randint(1, 500)), f"{r.uniform(0, 50):.3f}", "0",
        " 7 ", "3abc", "-2", "", "abc", "1e2", ".5", "Infinity",
    ] + [str(r.randint(1, 30))] * 30)


def make_csv(r: random.Random) -> str:
    cols = ["ACCTNO", "ACNAME", "PERDANA_FLAG", "STAFF_FLAG", "FINAL_CHANCES", "BRANCH"]
    if r.random() < 0.5:
        r.shuffle(cols)
    if r.random() < 0.04:
        cols.remove(r.choice(cols))  # missing column -> alert / undefined label
    header = "|".join(f" {c} " if r.random() < 0.1 else c for c in cols)
    malformed = r.random() < 0.1  # a few files carry a short / broken row
    messy = r.random() < 0.3      # odd FINAL_CHANCES values
    rows = []
    for i in range(r.choice([0, 1, 3, 10, 40, 120, 400, 800, 800, 1500, 1500, 3000])):
        values = {
            "ACCTNO": f"{r.randint(10**9, 10**10 - 1)}",
            "ACNAME": r.choice(["Ali bin Abu", "Siti Nur", "Lee Wei", "Raj Kumar", "Hjh Aminah"]) + f" {i}",
            "PERDANA_FLAG": r.choice(["Y", "N", "Y", "N", " Y ", "y"]),
            "STAFF_FLAG": r.choice(["N"] * 8 + ["Y", "Y", " N", "X"]),
            "FINAL_CHANCES": _chance(r) if messy else str(r.randint(1, 30)),
            "BRANCH": r.choice(["BSB", "KB", "TUT", "TEM"]),
        }
        row = [values[c] for c in cols]
        if malformed and r.random() < 0.01:
            row = row[: r.randint(0, len(row) - 1)]  # short / malformed row
        rows.append("|".join(row))
    newline = "\r\n" if r.random() < 0.15 else "\n"
    text = newline.join([header, *rows])
    if r.random() < 0.6:
        text += newline
    return text


def make_case(r: random.Random) -> dict:
    staff = r.random() < 0.3
    count = lambda: r.choice(["0", "1", "2", "3", "5", "8", "12", "25", "70", "", "4.9", "-1"]
                             + ["1", "2", "3", "5", "10"] * 3)
    return {
        "kind": "draw",
        "mode": "staff" if staff else "public",
        "content": make_csv(r),
        "seed": r.choice(SEEDS + ["".join(format(r.randrange(256), "x") for _ in range(16))] * 6),
        "perdana": count(),
        "mass": count(),
        "staff": count(),
        "showName": r.random() < 0.5,
        "showCert": r.random() < 0.5,
        "hash": "deadbeef",
    }


def run_python(case: dict):
    try:
        if case["mode"] == "staff":
            result = pick_staff(case["content"], parse_int(case["staff"]), case["seed"],
                                case["showName"], case["showCert"])
        else:
            result = pick_winners(case["content"], parse_int(case["perdana"]),
                                  parse_int(case["mass"]), case["seed"],
                                  case["showName"], case["showCert"])
    except DrawError:
        return None
    return result


@pytest.mark.parametrize("batch", range(6))
def test_draws_match_original(batch):
    r = random.Random(1000 + batch)
    cases = [make_case(r) for _ in range(150)]
    refs = run_reference(cases)
    outcomes = {"ok": 0, "error": 0}
    for case, ref in zip(cases, refs):
        result = run_python(case)
        ref_failed = bool(ref["alerts"]) or ref["error"] is not None
        if ref_failed:
            assert result is None, (case, ref)
            outcomes["error"] += 1
            continue
        assert result is not None, (case, ref)
        assert [w.label for w in result.winners] == ref["display"]
        assert [w.line for w in result.winners] == ref["picked"]
        assert result.headers == ref["headers"]
        assert results_csv(result.headers, [w.line for w in result.winners],
                           case["seed"], case["hash"]) == ref["download"]
        outcomes["ok"] += 1
    # make sure the generator exercises real draws, not just error paths
    assert outcomes["ok"] > 50, outcomes
