"""Slack bot (Socket Mode) — the mediator's Slack surface.

Commands (by mentioning the bot):
  @Mediator start <topic>   – start a new dispute in the channel
  @Mediator decide          – force a decision
  @Mediator status          – who has spoken, where the dispute stands
  @Mediator reset           – clear the session

Every other message written to the channel is part of the dispute while the
session is active. The mediator does NOT reply to every message immediately: by
default it speaks when mentioned, or when both parties have spoken since the last
mediator message — so it doesn't talk over the parties.

Run:  python -m mediator.adapters.slack_app
"""

import os
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from ..engine import MediatorEngine
from ..session import SessionStore
from ..commands import handle_command, handle_participant_message

engine = MediatorEngine(os.environ.get("MEDIATOR_CONFIG", "config.yaml"))
store = SessionStore()

app = App(token=os.environ["SLACK_BOT_TOKEN"])
BOT_USER_ID = None  # filled in on first event


@app.event("message")
def handle_message(body, say, client):
    global BOT_USER_ID
    event = body.get("event", {})
    if event.get("subtype") or event.get("bot_id"):
        return  # skip bot and system messages

    if BOT_USER_ID is None:
        BOT_USER_ID = client.auth_test()["user_id"]

    channel = event["channel"]
    user_id = event.get("user", "")
    text = (event.get("text") or "").strip()
    session = store.get(channel)

    mentioned = f"<@{BOT_USER_ID}>" in text
    clean = re.sub(rf"<@{BOT_USER_ID}>", "", text).strip()

    # ---- commands ---------------------------------------------------------
    if mentioned:
        replies = handle_command(engine, session, clean)
        if replies is not None:
            for r in replies:
                say(r)
            return

    # ---- normal dispute message -------------------------------------------
    replies = handle_participant_message(
        engine,
        session,
        user_id=user_id,
        fallback_name=f"<@{user_id}>",
        text=clean if mentioned else text,
        mentioned=mentioned,
    )
    for r in replies:
        say(r)


def main() -> None:
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("Mediator bot running (Slack Socket Mode)…")
    handler.start()


if __name__ == "__main__":
    main()
