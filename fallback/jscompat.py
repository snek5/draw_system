"""Exact Python re-implementations of the JavaScript behaviour the original
React draw relied on.

The draw must give the *same winners for the same seed* as the old browser
app, so these are bug-for-bug ports, not idiomatic Python:

* ``SeedRandom`` - seedrandom 3.0.5 (ARC4), the RNG behind ``seedrandom(seed)``.
* ``v8_sort`` - V8's Array.prototype.sort (TimSort, array-sort.tq). The old
  code shuffled winners with ``arr.sort(() => rng() - 0.5)``, so the order of
  comparator calls decides both the shuffle and how many RNG values are used.
* ``js_trim`` / ``parse_float`` / ``parse_int`` / ``js_get`` - JS string and
  number semantics (``undefined`` reads, ``parseFloat`` prefix parsing, ...).

Python floats are IEEE-754 doubles, so float arithmetic below matches JS.
tests/test_parity.py checks all of this against the original code in Node.
"""

from __future__ import annotations

import re
from typing import Callable, List, Sequence, TypeVar

T = TypeVar("T")


class JSTypeError(Exception):
    """Raised where the JavaScript code would have thrown a TypeError
    (typically calling ``.trim()`` / ``.split()`` on ``undefined``)."""


class _Undefined:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "undefined"


UNDEFINED = _Undefined()


def js_get(seq: Sequence[T], index: int):
    """``arr[index]`` with JS semantics: out of range (including negative
    indexes such as ``arr[-1]`` from a failed ``indexOf``) is ``undefined``."""
    if 0 <= index < len(seq):
        return seq[index]
    return UNDEFINED


# String.prototype.trim strips WhiteSpace and LineTerminator code points.
_JS_WHITESPACE = (
    "\t\n\v\f\r          "
    "        　﻿"
)


def js_trim(value) -> str:
    if value is UNDEFINED:
        raise JSTypeError("Cannot read properties of undefined (reading 'trim')")
    return value.strip(_JS_WHITESPACE)


def js_split(value, sep: str) -> List[str]:
    if value is UNDEFINED:
        raise JSTypeError("Cannot read properties of undefined (reading 'split')")
    return value.split(sep)


_FLOAT_PREFIX = re.compile(
    r"[+-]?(?:Infinity|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
)
_INT_PREFIX = re.compile(r"[+-]?\d+")


def parse_float(value: str) -> float:
    """JS ``parseFloat``: parse the longest numeric prefix, else NaN."""
    match = _FLOAT_PREFIX.match(value.lstrip(_JS_WHITESPACE))
    if not match:
        return float("nan")
    text = match.group(0)
    if text.endswith("Infinity"):
        return float("-inf") if text.startswith("-") else float("inf")
    return float(text)


def parse_int(value) -> float:
    """JS ``parseInt(value)`` (radix 10 for decimal input). Returns a float so
    that NaN can be represented; callers compare it like JS does."""
    match = _INT_PREFIX.match(str(value).lstrip(_JS_WHITESPACE))
    if not match:
        return float("nan")
    return float(int(match.group(0)))


def _utf16_units(text: str) -> List[int]:
    data = text.encode("utf-16-le", "surrogatepass")
    return [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]


# --------------------------------------------------------------------------
# seedrandom 3.0.5 (ARC4)
# --------------------------------------------------------------------------

_WIDTH = 256
_MASK = _WIDTH - 1
_CHUNKS = 6
_STARTDENOM = float(_WIDTH ** _CHUNKS)
_SIGNIFICANCE = float(2 ** 52)
_OVERFLOW = _SIGNIFICANCE * 2


class SeedRandom:
    """``seedrandom(seed)`` for a string seed. Call the instance for the next
    double in [0, 1)."""

    def __init__(self, seed: str):
        key = self._mixkey(seed)
        if not key:
            key = [0]
        s = list(range(_WIDTH))
        j = 0
        for i in range(_WIDTH):
            t = s[i]
            j = _MASK & (j + key[i % len(key)] + t)
            s[i] = s[j]
            s[j] = t
        self._s = s
        self._i = 0
        self._j = 0
        self._discard(_WIDTH)  # RC4-drop[256]

    @staticmethod
    def _mixkey(seed: str) -> List[int]:
        key: List[int] = []
        smear = 0  # `undefined ^ NaN` is 0 in JS
        for j, unit in enumerate(_utf16_units(seed)):
            idx = _MASK & j
            if idx < len(key):
                smear ^= key[idx] * 19
                key[idx] = _MASK & (smear + unit)
            else:  # key[idx] is undefined: smear ^= NaN leaves smear unchanged
                key.append(_MASK & (smear + unit))
        return key

    def _next_byte(self) -> int:
        s = self._s
        self._i = i = _MASK & (self._i + 1)
        t = s[i]
        self._j = j = _MASK & (self._j + t)
        s[i] = s[j]
        s[j] = t
        return s[_MASK & (s[i] + s[j])]

    def _discard(self, count: int) -> None:
        for _ in range(count):
            self._next_byte()

    def _g(self, count: int) -> int:
        r = 0
        for _ in range(count):
            r = r * _WIDTH + self._next_byte()
        return r

    def __call__(self) -> float:
        n = float(self._g(_CHUNKS))
        d = _STARTDENOM
        x = 0
        while n < _SIGNIFICANCE:
            n = (n + x) * _WIDTH
            d *= _WIDTH
            x = self._g(1)
        while n >= _OVERFLOW:
            n /= 2
            d /= 2
            x >>= 1
        return (n + x) / d


# --------------------------------------------------------------------------
# V8 Array.prototype.sort (third_party/v8/builtins/array-sort.tq)
# --------------------------------------------------------------------------

_MIN_GALLOP_WINS = 7


class _SortState:
    def __init__(self, array: list, compare: Callable[[T, T], float]):
        self.array = array
        self._compare = compare
        self.min_gallop = _MIN_GALLOP_WINS
        self.runs: List[List[int]] = []  # [base, length]

    def cmp(self, x, y) -> float:
        v = self._compare(x, y)
        if v != v:  # NaN -> 0
            return 0
        return v

    # -- galloping ---------------------------------------------------------

    def gallop_left(self, array, key, base, length, hint) -> int:
        last_ofs = 0
        offset = 1
        if self.cmp(array[base + hint], key) < 0:
            max_ofs = length - hint
            while offset < max_ofs:
                if self.cmp(array[base + hint + offset], key) >= 0:
                    break
                last_ofs = offset
                offset = (offset << 1) + 1
            if offset > max_ofs:
                offset = max_ofs
            last_ofs += hint
            offset += hint
        else:
            max_ofs = hint + 1
            while offset < max_ofs:
                if self.cmp(array[base + hint - offset], key) < 0:
                    break
                last_ofs = offset
                offset = (offset << 1) + 1
            if offset > max_ofs:
                offset = max_ofs
            last_ofs, offset = hint - offset, hint - last_ofs
        last_ofs += 1
        while last_ofs < offset:
            m = last_ofs + ((offset - last_ofs) >> 1)
            if self.cmp(array[base + m], key) < 0:
                last_ofs = m + 1
            else:
                offset = m
        return offset

    def gallop_right(self, array, key, base, length, hint) -> int:
        last_ofs = 0
        offset = 1
        if self.cmp(key, array[base + hint]) < 0:
            max_ofs = hint + 1
            while offset < max_ofs:
                if self.cmp(key, array[base + hint - offset]) >= 0:
                    break
                last_ofs = offset
                offset = (offset << 1) + 1
            if offset > max_ofs:
                offset = max_ofs
            last_ofs, offset = hint - offset, hint - last_ofs
        else:
            max_ofs = length - hint
            while offset < max_ofs:
                if self.cmp(key, array[base + hint + offset]) < 0:
                    break
                last_ofs = offset
                offset = (offset << 1) + 1
            if offset > max_ofs:
                offset = max_ofs
            last_ofs += hint
            offset += hint
        last_ofs += 1
        while last_ofs < offset:
            m = last_ofs + ((offset - last_ofs) >> 1)
            if self.cmp(key, array[base + m]) < 0:
                offset = m
            else:
                last_ofs = m + 1
        return offset

    # -- merging -----------------------------------------------------------

    def merge_low(self, base_a, length_a, base_b, length_b) -> None:
        work = self.array
        temp = work[base_a:base_a + length_a]
        dest = base_a
        cursor_temp = 0
        cursor_b = base_b

        work[dest] = work[cursor_b]
        dest += 1
        cursor_b += 1

        def succeed():
            if length_a > 0:
                work[dest:dest + length_a] = temp[cursor_temp:cursor_temp + length_a]

        def copy_b():
            work[dest:dest + length_b] = work[cursor_b:cursor_b + length_b]
            work[dest + length_b] = temp[cursor_temp]

        length_b -= 1
        if length_b == 0:
            return succeed()
        if length_a == 1:
            return copy_b()

        min_gallop = self.min_gallop
        while True:
            wins_a = 0
            wins_b = 0
            while True:
                if self.cmp(work[cursor_b], temp[cursor_temp]) < 0:
                    work[dest] = work[cursor_b]
                    dest += 1
                    cursor_b += 1
                    wins_b += 1
                    length_b -= 1
                    wins_a = 0
                    if length_b == 0:
                        return succeed()
                    if wins_b >= min_gallop:
                        break
                else:
                    work[dest] = temp[cursor_temp]
                    dest += 1
                    cursor_temp += 1
                    wins_a += 1
                    length_a -= 1
                    wins_b = 0
                    if length_a == 1:
                        return copy_b()
                    if wins_a >= min_gallop:
                        break

            min_gallop += 1
            first = True
            while wins_a >= _MIN_GALLOP_WINS or wins_b >= _MIN_GALLOP_WINS or first:
                first = False
                min_gallop = max(1, min_gallop - 1)
                self.min_gallop = min_gallop

                wins_a = self.gallop_right(temp, work[cursor_b], cursor_temp, length_a, 0)
                if wins_a > 0:
                    work[dest:dest + wins_a] = temp[cursor_temp:cursor_temp + wins_a]
                    dest += wins_a
                    cursor_temp += wins_a
                    length_a -= wins_a
                    if length_a == 1:
                        return copy_b()
                    if length_a == 0:
                        return succeed()
                work[dest] = work[cursor_b]
                dest += 1
                cursor_b += 1
                length_b -= 1
                if length_b == 0:
                    return succeed()

                wins_b = self.gallop_left(work, temp[cursor_temp], cursor_b, length_b, 0)
                if wins_b > 0:
                    work[dest:dest + wins_b] = work[cursor_b:cursor_b + wins_b]
                    dest += wins_b
                    cursor_b += wins_b
                    length_b -= wins_b
                    if length_b == 0:
                        return succeed()
                work[dest] = temp[cursor_temp]
                dest += 1
                cursor_temp += 1
                length_a -= 1
                if length_a == 1:
                    return copy_b()
            min_gallop += 1
            self.min_gallop = min_gallop

    def merge_high(self, base_a, length_a, base_b, length_b) -> None:
        work = self.array
        temp = work[base_b:base_b + length_b]
        dest = base_b + length_b - 1
        cursor_temp = length_b - 1
        cursor_a = base_a + length_a - 1

        work[dest] = work[cursor_a]
        dest -= 1
        cursor_a -= 1

        def succeed():
            if length_b > 0:
                start = dest - (length_b - 1)
                work[start:start + length_b] = temp[0:length_b]

        def copy_a():
            d = dest - length_a
            c = cursor_a - length_a
            work[d + 1:d + 1 + length_a] = work[c + 1:c + 1 + length_a]
            work[d] = temp[cursor_temp]

        length_a -= 1
        if length_a == 0:
            return succeed()
        if length_b == 1:
            return copy_a()

        min_gallop = self.min_gallop
        while True:
            wins_a = 0
            wins_b = 0
            while True:
                if self.cmp(temp[cursor_temp], work[cursor_a]) < 0:
                    work[dest] = work[cursor_a]
                    dest -= 1
                    cursor_a -= 1
                    wins_a += 1
                    length_a -= 1
                    wins_b = 0
                    if length_a == 0:
                        return succeed()
                    if wins_a >= min_gallop:
                        break
                else:
                    work[dest] = temp[cursor_temp]
                    dest -= 1
                    cursor_temp -= 1
                    wins_b += 1
                    length_b -= 1
                    wins_a = 0
                    if length_b == 1:
                        return copy_a()
                    if wins_b >= min_gallop:
                        break

            min_gallop += 1
            first = True
            while wins_a >= _MIN_GALLOP_WINS or wins_b >= _MIN_GALLOP_WINS or first:
                first = False
                min_gallop = max(1, min_gallop - 1)
                self.min_gallop = min_gallop

                k = self.gallop_right(work, temp[cursor_temp], base_a, length_a, length_a - 1)
                wins_a = length_a - k
                if wins_a > 0:
                    dest -= wins_a
                    cursor_a -= wins_a
                    work[dest + 1:dest + 1 + wins_a] = work[cursor_a + 1:cursor_a + 1 + wins_a]
                    length_a -= wins_a
                    if length_a == 0:
                        return succeed()
                work[dest] = temp[cursor_temp]
                dest -= 1
                cursor_temp -= 1
                length_b -= 1
                if length_b == 1:
                    return copy_a()

                k = self.gallop_left(temp, work[cursor_a], 0, length_b, length_b - 1)
                wins_b = length_b - k
                if wins_b > 0:
                    dest -= wins_b
                    cursor_temp -= wins_b
                    work[dest + 1:dest + 1 + wins_b] = temp[cursor_temp + 1:cursor_temp + 1 + wins_b]
                    length_b -= wins_b
                    if length_b == 1:
                        return copy_a()
                    if length_b == 0:
                        return succeed()
                work[dest] = work[cursor_a]
                dest -= 1
                cursor_a -= 1
                length_a -= 1
                if length_a == 0:
                    return succeed()
            min_gallop += 1
            self.min_gallop = min_gallop

    def merge_at(self, i: int) -> None:
        runs = self.runs
        base_a, length_a = runs[i]
        base_b, length_b = runs[i + 1]
        runs[i][1] = length_a + length_b
        del runs[i + 1]

        work = self.array
        k = self.gallop_right(work, work[base_b], base_a, length_a, 0)
        base_a += k
        length_a -= k
        if length_a == 0:
            return
        length_b = self.gallop_left(work, work[base_a + length_a - 1], base_b, length_b, length_b - 1)
        if length_b == 0:
            return
        if length_a <= length_b:
            self.merge_low(base_a, length_a, base_b, length_b)
        else:
            self.merge_high(base_a, length_a, base_b, length_b)

    def _invariant(self, n: int) -> bool:
        if n < 2:
            return True
        runs = self.runs
        return runs[n - 2][1] > runs[n - 1][1] + runs[n][1]

    def merge_collapse(self) -> None:
        runs = self.runs
        while len(runs) > 1:
            n = len(runs) - 2
            if not self._invariant(n + 1) or not self._invariant(n):
                if runs[n - 1][1] < runs[n + 1][1]:
                    n -= 1
                self.merge_at(n)
            elif runs[n][1] <= runs[n + 1][1]:
                self.merge_at(n)
            else:
                break

    def merge_force_collapse(self) -> None:
        runs = self.runs
        while len(runs) > 1:
            n = len(runs) - 2
            if n > 0 and runs[n - 1][1] < runs[n + 1][1]:
                n -= 1
            self.merge_at(n)

    # -- runs ----------------------------------------------------------------

    def binary_insertion_sort(self, low, start, high) -> None:
        work = self.array
        if low == start:
            start += 1
        while start < high:
            left = low
            right = start
            pivot = work[start]
            while left < right:
                mid = left + ((right - left) >> 1)
                if self.cmp(pivot, work[mid]) < 0:
                    right = mid
                else:
                    left = mid + 1
            work[left + 1:start + 1] = work[left:start]
            work[left] = pivot
            start += 1

    def count_and_make_run(self, low_arg, high) -> int:
        work = self.array
        low = low_arg + 1
        if low == high:
            return 1
        run_length = 2
        element_low = work[low]
        descending = self.cmp(element_low, work[low - 1]) < 0
        previous = element_low
        for idx in range(low + 1, high):
            current = work[idx]
            order = self.cmp(current, previous)
            if descending:
                if order >= 0:
                    break
            elif order < 0:
                break
            previous = current
            run_length += 1
        if descending:
            work[low_arg:low_arg + run_length] = work[low_arg:low_arg + run_length][::-1]
        return run_length


def _min_run_length(n: int) -> int:
    r = 0
    while n >= 64:
        r |= n & 1
        n >>= 1
    return n + r


def v8_sort(array: list, compare: Callable[[T, T], float]) -> list:
    """Sort ``array`` in place exactly as V8's ``Array.prototype.sort`` would
    with comparator ``compare``, calling it in the same order. Returns it."""
    length = len(array)
    if length < 2:
        return array
    state = _SortState(array, compare)
    remaining = length
    low = 0
    min_run = _min_run_length(remaining)
    while remaining != 0:
        run = state.count_and_make_run(low, low + remaining)
        if run < min_run:
            forced = min(min_run, remaining)
            state.binary_insertion_sort(low, low + run, low + forced)
            run = forced
        state.runs.append([low, run])
        state.merge_collapse()
        low += run
        remaining -= run
    state.merge_force_collapse()
    return array
