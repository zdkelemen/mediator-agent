"""Microsoft Teams bot — the mediator's Teams surface.

Built on the Bot Framework SDK. Teams delivers activities to an HTTPS endpoint
(``POST /api/messages``); this module runs a small aiohttp server for that.

Commands (by @mentioning the bot in a group chat / channel, or just typing them
in a 1:1 chat):
  @Mediator start <topic>   – start a new dispute in the conversation
  @Mediator decide          – force a decision
  @Mediator status          – who has spoken, where the dispute stands
  @Mediator reset           – clear the session

The mediation behaviour is identical to the Slack adapter — all shared logic
lives in ``mediator.commands``.

Setup (high level):
  1. Create an Azure Bot resource; note its Microsoft App ID + create a secret.
  2. Set the messaging endpoint to https://<your-host>/api/messages
     (use a tunnel such as `dev tunnels` / ngrok while developing).
  3. Add the Teams channel to the bot, then sideload/install the app in Teams.
  4. Fill MICROSOFT_APP_ID / MICROSOFT_APP_PASSWORD (see .env.example).

Run:  python -m mediator.adapters.teams_app
"""

import os
import sys
import traceback

from aiohttp import web
from botbuilder.core import ActivityHandler, MessageFactory, TurnContext
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import (
    CloudAdapter,
    ConfigurationBotFrameworkAuthentication,
)
from botbuilder.schema import Activity, ChannelAccount

from ..engine import MediatorEngine
from ..session import SessionStore
from ..commands import handle_command, handle_participant_message


class _AppConfig:
    """Config object read by ConfigurationBotFrameworkAuthentication."""

    APP_ID = os.environ.get("MICROSOFT_APP_ID", "")
    APP_PASSWORD = os.environ.get("MICROSOFT_APP_PASSWORD", "")
    APP_TYPE = os.environ.get("MICROSOFT_APP_TYPE", "MultiTenant")
    APP_TENANTID = os.environ.get("MICROSOFT_APP_TENANT_ID", "")


class MediatorBot(ActivityHandler):
    def __init__(self, engine: MediatorEngine, store: SessionStore) -> None:
        self.engine = engine
        self.store = store

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        activity = turn_context.activity
        channel = activity.conversation.id
        session = self.store.get(channel)

        # In a group chat / channel the bot only receives messages that mention it;
        # in a 1:1 personal chat every message arrives, so treat those as addressed.
        is_personal = (activity.conversation.conversation_type or "").lower() == "personal"
        mentioned = is_personal or self._is_mentioned(turn_context)

        # Strip the bot @mention from the text.
        clean = TurnContext.remove_recipient_mention(activity) or ""
        clean = clean.strip()

        frm: ChannelAccount = activity.from_property
        user_id = getattr(frm, "aad_object_id", None) or frm.id
        fallback_name = frm.name or user_id

        # ---- commands -----------------------------------------------------
        if mentioned:
            replies = handle_command(self.engine, session, clean)
            if replies is not None:
                for r in replies:
                    await turn_context.send_activity(MessageFactory.text(r))
                return

        # ---- normal dispute message ---------------------------------------
        replies = handle_participant_message(
            self.engine,
            session,
            user_id=user_id,
            fallback_name=fallback_name,
            text=clean,
            mentioned=mentioned,
        )
        for r in replies:
            await turn_context.send_activity(MessageFactory.text(r))

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ) -> None:
        bot_id = turn_context.activity.recipient.id
        for member in members_added:
            if member.id != bot_id:
                await turn_context.send_activity(
                    MessageFactory.text(
                        "👋 I'm the mediator. Start a dispute with "
                        "`@Mediator start <topic>`."
                    )
                )

    @staticmethod
    def _is_mentioned(turn_context: TurnContext) -> bool:
        bot_id = turn_context.activity.recipient.id
        for entity in turn_context.activity.entities or []:
            if entity.type == "mention":
                mentioned = getattr(entity, "properties", {}).get("mentioned", {})
                if mentioned.get("id") == bot_id:
                    return True
        return False


# --- aiohttp wiring --------------------------------------------------------
ADAPTER = CloudAdapter(ConfigurationBotFrameworkAuthentication(_AppConfig()))
BOT = MediatorBot(
    MediatorEngine(os.environ.get("MEDIATOR_CONFIG", "config.yaml")),
    SessionStore(),
)


async def _on_error(context: TurnContext, error: Exception) -> None:
    print(f"\n[on_turn_error] {error}", file=sys.stderr)
    traceback.print_exc()
    await context.send_activity("Sorry, the mediator hit an error handling that message.")


ADAPTER.on_turn_error = _on_error


async def messages(req: web.Request) -> web.Response:
    return await ADAPTER.process(req, BOT)


def create_app() -> web.Application:
    app = web.Application(middlewares=[aiohttp_error_middleware])
    app.router.add_post("/api/messages", messages)
    return app


def main() -> None:
    port = int(os.environ.get("PORT", 3978))
    print(f"Mediator bot running (Microsoft Teams) on http://localhost:{port}/api/messages")
    web.run_app(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
