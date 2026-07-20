"""Generic HTTP webhook adapter — no Azure Bot, no vendor SDK.

This is the platform-neutral surface: a tiny aiohttp server that accepts a
message over plain JSON and returns the mediator's replies as JSON. Anything that
can POST JSON can drive the mediator with it — a **Microsoft Teams** flow built in
Power Automate / Workflows (trigger on a new channel message → POST here → post the
replies back with a "Post message in a chat or channel" action), a Slack/Discord/
Mattermost bridge, a cron job, or your own app. No Azure Bot resource required.

Endpoints
---------
POST /message
    Request JSON:
      {
        "channel_id": "team-42",         # required — the conversation/session key
        "user_id":    "u123",            # required — platform user id (maps to a role)
        "name":       "Kata",            # optional — display name fallback
        "text":       "we must ship Q3", # required — the message
        "mentioned":  true               # optional (default true) — was the bot addressed?
      }
    Response JSON: {"replies": ["...", ...]}  (empty list = the mediator stayed silent)

GET /health → {"status": "ok"}

Auth (optional): set MEDIATOR_WEBHOOK_TOKEN and send it as the `X-Mediator-Token`
header (or `?token=`); requests without a matching token get 401.

Run:  python -m mediator.adapters.webhook_app   (listens on $PORT, default 3979)
"""

import os

from aiohttp import web

from ..engine import MediatorEngine
from ..session import SessionStore
from ..commands import handle_command, handle_participant_message

engine = MediatorEngine(os.environ.get("MEDIATOR_CONFIG", "config.yaml"))
store = SessionStore()

_TOKEN = os.environ.get("MEDIATOR_WEBHOOK_TOKEN")


def _authorized(request: web.Request) -> bool:
    if not _TOKEN:
        return True  # no token configured → open endpoint
    supplied = request.headers.get("X-Mediator-Token") or request.query.get("token")
    return supplied == _TOKEN


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def message(request: web.Request) -> web.Response:
    if not _authorized(request):
        return web.json_response({"error": "unauthorized"}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    channel_id = body.get("channel_id")
    text = body.get("text")
    if not channel_id or text is None:
        return web.json_response(
            {"error": "channel_id and text are required"}, status=400
        )

    user_id = body.get("user_id") or "anonymous"
    name = body.get("name") or user_id
    mentioned = bool(body.get("mentioned", True))

    session = store.get(channel_id)
    replies: list[str] = []

    # Treat an addressed message as a possible command first (start/decide/…).
    if mentioned:
        cmd = handle_command(engine, session, str(text).strip())
        if cmd is not None:
            return web.json_response({"replies": cmd})

    replies = handle_participant_message(
        engine,
        session,
        user_id=user_id,
        fallback_name=name,
        text=str(text),
        mentioned=mentioned,
    )
    return web.json_response({"replies": replies})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/message", message)
    app.router.add_get("/health", health)
    return app


def main() -> None:
    port = int(os.environ.get("PORT", 3979))
    print(f"Mediator webhook adapter running on http://0.0.0.0:{port}  (POST /message)")
    web.run_app(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
