"""Per-browser draw state, kept in this process's memory.

The participant file (names, account numbers) is never written to disk; the
browser session only carries a random id. This assumes the app runs as a
single process on the draw machine, as the old in-browser app effectively did.
Restarting the server clears everything.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .draw import DrawResult


@dataclass
class Session:
    file_bytes: Optional[bytes] = None
    file_hash: str = ""
    seed: str = ""
    # draw settings, captured on Submit
    staff_draw: bool = False
    show_name: bool = False
    show_cert: bool = False
    vip: float = 0.0
    mass: float = 0.0
    staff: float = 0.0
    delay: float = 0.0
    submitted: bool = False
    # draw outcome
    result: Optional[DrawResult] = None
    revealed: int = 0            # winners shown so far (in reveal order)
    picked_lines: List[str] = field(default_factory=list)


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, Session] = {}

    def new(self) -> tuple[str, Session]:
        key = uuid.uuid4().hex
        state = Session()
        with self._lock:
            self._sessions[key] = state
        return key, state

    def get(self, key: Optional[str]) -> Optional[Session]:
        if not key:
            return None
        with self._lock:
            return self._sessions.get(key)

    def drop(self, key: Optional[str]) -> None:
        with self._lock:
            self._sessions.pop(key or "", None)


store = Store()
