"""CLI mode — try the mediator without any chat platform.

Usage:
    python -m mediator.cli

Message format at the prompt:
    kata: Feature X has to ship in Q3
    gabor: The payment module can't handle it without a refactor first
    /decide   – request a decision
    /reset    – new dispute
    /exit     – quit

Names are mapped to roles by the config.yaml participants section
(by name, case-insensitively); an unknown name gets the default_role.
"""

import os
import sys

from .engine import MediatorEngine
from .session import Session


def main() -> None:
    engine = MediatorEngine(os.environ.get("MEDIATOR_CONFIG", "config.yaml"))
    name_to_role = {
        p["name"].lower(): (p["name"], p["role"])
        for p in (engine.config.get("participants") or {}).values()
    }

    session = Session(channel_id="cli")
    session.reset()
    session.topic = input("Dispute topic: ").strip() or "(not provided)"
    session.active = True
    session.save()

    print("\nFormat: 'name: message' | commands: /decide /reset /exit\n")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line.lower() in ("/exit", "/quit"):
            break
        if line.lower() == "/reset":
            session.reset()
            session.topic = input("New topic: ").strip()
            session.active = True
            session.save()
            continue
        if line.lower() in ("/decide", "/decision"):
            print("\n--- MEDIATOR ---")
            print(engine.respond(session, force_decision=True), "\n")
            continue

        if ":" not in line:
            print("Format: 'name: message'")
            continue
        raw_name, text = line.split(":", 1)
        name, role = name_to_role.get(
            raw_name.strip().lower(),
            (raw_name.strip().capitalize(), engine.config.get("default_role", "Participant")),
        )
        session.add_message(name, role, text.strip())

        print("\n--- MEDIATOR ---")
        print(engine.respond(session), "\n")

    print("Bye!")
    sys.exit(0)


if __name__ == "__main__":
    main()
