"""Per-channel dispute session state (in-memory + JSON persistence)."""

import hashlib
import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
STATE_DIR.mkdir(exist_ok=True)


def _safe_filename(channel_id: str) -> str:
    """Map an arbitrary channel/conversation id to a filesystem-safe name.

    Teams conversation ids contain characters (``:`` ``/`` ...) that are illegal
    in Windows filenames, so we slugify and append a short hash to keep it unique.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]", "_", channel_id)[:80]
    digest = hashlib.sha1(channel_id.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}.json"

# Language-neutral sentinel marking a message authored by the mediator itself.
MEDIATOR_ROLE = "mediator"
MEDIATOR_NAME = "Mediator"


@dataclass
class Session:
    channel_id: str
    topic: str = ""
    messages: list = field(default_factory=list)   # [{"speaker","role","text","ts"}]
    active: bool = False
    decided: bool = False
    started_at: float = 0.0

    # --- protocol guards ---------------------------------------------------
    def speakers(self) -> set[str]:
        return {m["speaker"] for m in self.messages if m["role"] != MEDIATOR_ROLE}

    def everyone_spoke_at_least(self, n: int = 1) -> bool:
        counts: dict[str, int] = {}
        for m in self.messages:
            if m["role"] != MEDIATOR_ROLE:
                counts[m["speaker"]] = counts.get(m["speaker"], 0) + 1
        return len(counts) >= 2 and all(v >= n for v in counts.values())

    def decision_allowed(self) -> bool:
        """Code-level guard: at least 2 parties, each spoke at least twice
        (first the position, then the reaction to the other's arguments)."""
        return self.everyone_spoke_at_least(2)

    # --- messages ----------------------------------------------------------
    def add_message(self, speaker: str, role: str, text: str) -> None:
        self.messages.append(
            {"speaker": speaker, "role": role, "text": text, "ts": time.time()}
        )
        self.save()

    def api_messages(self) -> list[dict]:
        """Claude API messages format: participants = user, mediator = assistant."""
        out: list[dict] = []
        for m in self.messages:
            if m["role"] == MEDIATOR_ROLE:
                out.append({"role": "assistant", "content": m["text"]})
            else:
                out.append(
                    {
                        "role": "user",
                        "content": f"[{m['role']} – {m['speaker']}]: {m['text']}",
                    }
                )
        # The API must start with a user message; alternating roles are not
        # required, but we merge consecutive same-role blocks.
        merged: list[dict] = []
        for msg in out:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n\n" + msg["content"]
            else:
                merged.append(dict(msg))
        return merged

    # --- persistence -------------------------------------------------------
    def _path(self) -> Path:
        return STATE_DIR / _safe_filename(self.channel_id)

    def save(self) -> None:
        self._path().write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, channel_id: str) -> "Session":
        p = STATE_DIR / _safe_filename(channel_id)
        if p.exists():
            data = json.loads(p.read_text())
            return cls(**data)
        return cls(channel_id=channel_id)

    def reset(self) -> None:
        self.topic = ""
        self.messages = []
        self.active = False
        self.decided = False
        self.started_at = 0.0
        self.save()


class SessionStore:
    """One session per channel; simple in-memory cache + file persistence."""

    def __init__(self) -> None:
        self._cache: dict[str, Session] = {}

    def get(self, channel_id: str) -> Session:
        if channel_id not in self._cache:
            self._cache[channel_id] = Session.load(channel_id)
        return self._cache[channel_id]
