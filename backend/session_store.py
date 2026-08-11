"""
In-memory session store for multi-turn conversations.

Keyed by session_id (a UUID the frontend keeps and reuses for the whole
chat). Each session holds the raw message history (for LLM context) and the
spec fields gathered so far across turns.
"""

_sessions = {}


def get_session(session_id):
    if session_id not in _sessions:
        _sessions[session_id] = {
            "messages": [],  # [{"role": "user"/"assistant", "content": "..."}]
            "spec": {},      # fields accumulated across turns
        }
    return _sessions[session_id]


def reset_session(session_id):
    _sessions.pop(session_id, None)