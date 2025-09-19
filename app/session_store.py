# ---------------------------
# File: app/session_store.py
# ---------------------------
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time
import threading


@dataclass
class SessionState:
    session_id: str
    created_at: float
    candidate_indices: List[int] = field(default_factory=list)
    initial_query: str = ""
    current_question: Optional[Dict[str, Any]] = None
    question_history: List[Dict[str, Any]] = field(default_factory=list)
    final_result_index: Optional[int] = None  # index into QueryAgent.df


class SessionStore:
    """A very small in-memory session store. Not persistent.
    For production use replace with Redis or a database-backed session store.
    """
    def __init__(self):
        self._store: Dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def create_session(self, session_id: str, candidate_indices: List[int], initial_query: str) -> SessionState:
        with self._lock:
            s = SessionState(session_id=session_id, created_at=time.time(), candidate_indices=candidate_indices, initial_query=initial_query)
            self._store[session_id] = s
            return s

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._store.get(session_id)

    def update(self, session_id: str, **kwargs):
        with self._lock:
            s = self._store.get(session_id)
            if not s:
                return None
            for k, v in kwargs.items():
                setattr(s, k, v)
            return s

    def delete(self, session_id: str):
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]


# Singleton store
session_store = SessionStore()