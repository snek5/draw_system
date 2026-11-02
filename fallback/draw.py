"""The prize draw, ported bug-for-bug from the original ``helpers.js``.

Given the same CSV and RNG seed, ``pick_winners`` / ``pick_staff`` choose the
same winners, in the same reveal order, with the same labels as the old React
app, so earlier draws stay reproducible. Known quirks of the original weighted
pick (stale cumulative weights after each pick, a hit on an ineligible row
going to the next eligible one, possible crash when no row qualifies) are kept
on purpose; see README.md.

Where the original showed an ``alert`` or threw, these functions raise
``DrawError``.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from typing import List

from .jscompat import (
    JSTypeError,
    SeedRandom,
    js_get,
    js_split,
    js_trim,
    parse_float,
    v8_sort,
)


class DrawError(Exception):
    """The draw could not run; the message is safe to show the operator."""


@dataclass
class Winner:
    number: int    # the N in "WN:" (1-based position in reveal order)
    label: str     # text shown on screen
    line: str      # the raw CSV line, as written to the download


@dataclass
class DrawResult:
    headers: List[str]
    winners: List[Winner] = field(default_factory=list)


# --------------------------------------------------------------------------
# Upload: hash + seed  (hashFile)
# --------------------------------------------------------------------------

def hash_file(data: bytes) -> str:
    """SHA-256 of the raw uploaded bytes, lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def new_seed() -> str:
    """16 random bytes, each written as hex *without* zero padding - the
    original's ``byte.toString(16)`` - so seeds are 16 to 32 characters."""
    return "".join(format(b, "x") for b in secrets.token_bytes(16))


def decode_csv(data: bytes) -> str:
    """Decode like ``FileReader.readAsText``: UTF-8, BOM stripped, invalid
    bytes replaced."""
    return data.decode("utf-8-sig", errors="replace")


# --------------------------------------------------------------------------
# Draws  (pickWinners / pickStaff)
# --------------------------------------------------------------------------

def _count(value) -> int:
    """Loop bound from ``parseInt``: NaN or negative means no iterations."""
    if value != value or value <= 0:
        return 0
    return int(value)


def _field(line, index: int) -> str:
    return js_trim(js_get(js_split(line, "|"), index))


def _pick(data, cumulative, random_value, predicate) -> int:
    """``cumulativeChances.findIndex(...)`` from the original loop body:
    the first row whose (stale) cumulative weight reaches ``random_value``
    and that passes ``predicate``; -1 if none."""
    for i, value in enumerate(cumulative):
        if value >= random_value and predicate(data[i]):
            return i
    return -1


def _labels(rng_lines, headers, show_name, show_cert, default_is_name) -> List[Winner]:
    winners = []
    name_index = headers.index("ACNAME") if "ACNAME" in headers else -1
    cert_index = headers.index("ACCTNO") if "ACCTNO" in headers else -1
    for i, line in enumerate(rng_lines):
        n = i + 1
        try:
            parts = js_split(line, "|")
            name = js_trim(js_get(parts, name_index))
            cert = js_trim(js_get(parts, cert_index))
        except JSTypeError:
            # In the original this setTimeout callback threw: the winner was
            # never shown and never added to the download.
            continue
        if show_cert and show_name:
            label = f"W{n}: {name}\n{cert}"
        elif show_cert:
            label = f"W{n}: {cert}\n"
        elif show_name:
            label = f"W{n}: {name}\n"
        elif default_is_name:
            label = f"W{n}: {name}\n"
        else:
            label = f"W{n}: {cert}\n"
        winners.append(Winner(number=n, label=label, line=line))
    return winners


def pick_winners(content: str, vip_winners, mass_winners, seed: str,
                 show_name: bool, show_cert: bool) -> DrawResult:
    """Public draw: VIP winners first, then Mass Market, then shuffled.
    ``vip_winners``/``mass_winners`` are ``parse_int`` results."""
    lines = content.split("\n")
    headers = [js_trim(h) for h in lines[0].split("|")]
    data = lines[1:]

    rng = SeedRandom(seed)

    vip_index = headers.index("VIP_FLAG") if "VIP_FLAG" in headers else -1
    chance_index = headers.index("FINAL_CHANCES") if "FINAL_CHANCES" in headers else -1
    staff_index = headers.index("STAFF_FLAG") if "STAFF_FLAG" in headers else -1

    if vip_index == -1:
        raise DrawError('CSV file is missing the "VIP_FLAG" column.')
    if chance_index == -1:
        raise DrawError('CSV file is missing the "FINAL_CHANCES" column.')
    if staff_index == -1:
        raise DrawError('CSV file is missing the "STAFF_FLAG" column.')

    try:
        cumulative_sum = 0.0
        cumulative: List[float] = []
        for line in data:
            parts = line.split("|")
            value = 0.0
            if len(parts) > chance_index and js_trim(js_get(parts, staff_index)) == "N":
                chance = parse_float(js_trim(parts[chance_index]))
                if chance == chance and chance >= 0:
                    cumulative_sum += chance
                    value = cumulative_sum
            cumulative.append(value)
        total = cumulative_sum

        picked: List[str] = []

        def take(index):
            nonlocal cumulative_sum
            if index == -1:
                raise JSTypeError("Cannot read properties of undefined (reading 'split')")
            parts = data[index].split("|")
            picked.append(data[index])
            del data[index]
            cumulative_sum -= parse_float(js_trim(js_get(parts, chance_index)))
            del cumulative[index]

        def eligible(flag):
            return lambda line: (_field(line, vip_index) == flag
                                 and _field(line, staff_index) == "N")

        for _ in range(_count(vip_winners)):
            take(_pick(data, cumulative, rng() * total, eligible("Y")))
        for _ in range(_count(mass_winners)):
            take(_pick(data, cumulative, rng() * cumulative_sum, eligible("N")))
    except JSTypeError as exc:
        raise DrawError(
            "Not enough eligible entries for the requested winners, "
            "or the file has a malformed row."
        ) from exc

    v8_sort(picked, lambda a, b: rng() - 0.5)
    return DrawResult(headers=headers,
                      winners=_labels(picked, headers, show_name, show_cert,
                                      default_is_name=False))


def pick_staff(content: str, staff_winners, seed: str,
               show_name: bool, show_cert: bool) -> DrawResult:
    """Staff draw: every STAFF_FLAG=Y row has equal chance."""
    lines = content.split("\n")
    headers = [js_trim(h) for h in lines[0].split("|")]
    data = lines[1:]

    rng = SeedRandom(seed)

    staff_index = headers.index("STAFF_FLAG") if "STAFF_FLAG" in headers else -1
    if staff_index == -1:
        raise DrawError('CSV file is missing the "STAFF_FLAG" column.')

    try:
        cumulative_sum = 0.0
        cumulative: List[float] = []
        for line in data:
            parts = line.split("|")
            value = 0.0
            if len(parts) > staff_index and js_trim(parts[staff_index]) == "Y":
                cumulative_sum += 1
                value = cumulative_sum
            cumulative.append(value)
        total = cumulative_sum

        picked: List[str] = []
        for _ in range(_count(staff_winners)):
            index = _pick(data, cumulative, rng() * total,
                          lambda line: _field(line, staff_index) == "Y")
            if index == -1:
                raise JSTypeError("Cannot read properties of undefined (reading 'split')")
            picked.append(data[index])
            del data[index]
            cumulative_sum -= 1
            del cumulative[index]
    except JSTypeError as exc:
        raise DrawError(
            "Not enough eligible staff for the requested winners, "
            "or the file has a malformed row."
        ) from exc

    v8_sort(picked, lambda a, b: rng() - 0.5)
    return DrawResult(headers=headers,
                      winners=_labels(picked, headers, show_name, show_cert,
                                      default_is_name=True))


# --------------------------------------------------------------------------
# Download  (downloadSelectedLines)
# --------------------------------------------------------------------------

def results_csv(headers: List[str], picked_lines: List[str], seed: str, file_hash: str) -> str:
    final_line = f"RNG Seed = {seed} | File Hash = {file_hash}"
    return "\n".join(["|".join(headers), *picked_lines, final_line])
