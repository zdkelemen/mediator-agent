"""The mediator engine: provider-agnostic LLM call + protocol enforcement in code."""

import yaml

from .prompts import build_system_prompt, STEELMAN_NUDGE, FORCE_DECISION
from .session import Session, MEDIATOR_ROLE, MEDIATOR_NAME
from .llm import get_provider


class MediatorEngine:
    def __init__(self, config_path: str = "config.yaml") -> None:
        with open(config_path, encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.provider, self.model = get_provider(self.config)
        self.max_tokens = int(self.config.get("max_tokens", 1500))

    # --- participant resolution --------------------------------------------
    def resolve_participant(self, user_id: str, fallback_name: str) -> tuple[str, str]:
        p = (self.config.get("participants") or {}).get(user_id)
        if p:
            return p["name"], p["role"]
        return fallback_name, self.config.get("default_role", "Participant")

    def participants_map(self) -> dict[str, str]:
        return {
            p["name"]: p["role"]
            for p in (self.config.get("participants") or {}).values()
        }

    # --- main entry point --------------------------------------------------
    def respond(self, session: Session, force_decision: bool = False) -> str:
        system = build_system_prompt(
            topic=session.topic,
            participants=self.participants_map(),
            criteria=self.config["criteria"],
        )

        messages = session.api_messages()
        if not messages or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": "(The mediator is asked for a summary.)"})

        # Code-level protocol guard: the model only receives a "you may decide"
        # signal if the session state allows it, or the parties explicitly ask.
        if force_decision:
            messages[-1]["content"] += f"\n\n[SYSTEM]: {FORCE_DECISION}"
        elif not session.decision_allowed():
            messages[-1]["content"] += f"\n\n[SYSTEM]: {STEELMAN_NUDGE}"

        text = self.provider.complete(
            system=system,
            messages=messages,
            model=self.model,
            max_tokens=self.max_tokens,
        )

        session.add_message(MEDIATOR_NAME, MEDIATOR_ROLE, text)
        if "**DECISION:**" in text:
            session.decided = True
            session.save()
        return text
