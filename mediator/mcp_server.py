"""MCP server — makes the mediator usable from any agentic CLI.

Model Context Protocol (MCP) is spoken by Claude Code, Codex, Cursor, Windsurf and
other agentic CLIs. Exposing the mediator as an MCP server means the same auditable
mediation engine (recorded criteria, protocol guards, human-in-the-loop) can be driven
from inside any of them — the host CLI just calls these tools.

The mediation reasoning stays self-contained (it calls the Anthropic API internally),
so the governance core is identical no matter which CLI is at the wheel.

Register it with a CLI, e.g. Claude Code:

    claude mcp add mediator -- python -m mediator.mcp_server

or in an MCP client config (Codex, Cursor, …):

    {
      "mcpServers": {
        "mediator": {
          "command": "python",
          "args": ["-m", "mediator.mcp_server"],
          "env": { "ANTHROPIC_API_KEY": "sk-ant-...", "MEDIATOR_CONFIG": "config.yaml" }
        }
      }
    }

Run standalone (stdio):  python -m mediator.mcp_server
"""

import os

from mcp.server.fastmcp import FastMCP

from .engine import MediatorEngine
from .session import SessionStore

mcp = FastMCP("mediator")

_engine = MediatorEngine(os.environ.get("MEDIATOR_CONFIG", "config.yaml"))
_store = SessionStore()

# Sessions are namespaced so one server process can run several parallel disputes.
_PREFIX = "mcp:"


def _session(session_id: str):
    return _store.get(_PREFIX + (session_id or "default"))


def _register_participant(name: str, role: str) -> None:
    """Make a name→role mapping visible to the system prompt at runtime."""
    participants = _engine.config.setdefault("participants", {}) or {}
    _engine.config["participants"] = participants
    participants[f"name:{name.lower()}"] = {"name": name, "role": role}


@mcp.tool()
def start_mediation(
    topic: str,
    participants: list[dict] | None = None,
    session_id: str = "default",
) -> str:
    """Start (or restart) a mediation session.

    Args:
        topic: What the dispute is about.
        participants: Optional list of {"name": ..., "role": ...} to register the
            parties and their roles (e.g. Product Manager, Architect). If omitted,
            roles fall back to config.yaml / the default role.
        session_id: Name this dispute if you want to run several in parallel.

    Returns a confirmation and instructions for how to add statements.
    """
    session = _session(session_id)
    session.reset()
    session.topic = topic or "(not provided)"
    session.active = True
    for p in participants or []:
        if p.get("name"):
            _register_participant(p["name"], p.get("role", _engine.config.get("default_role", "Participant")))
    session.save()
    return (
        f"Mediation started on session '{session_id}'.\n"
        f"Topic: {session.topic}\n\n"
        "Use add_statement(speaker, text[, role]) for each party's message. "
        "The mediator will explore interests, request facts, steelman both sides, "
        "and only then recommend a decision. Call request_decision() to force one "
        "(uncertainties will be flagged)."
    )


@mcp.tool()
def add_statement(
    speaker: str,
    text: str,
    role: str | None = None,
    session_id: str = "default",
) -> str:
    """Record a participant's statement and get the mediator's response (if any).

    Args:
        speaker: The party's name (e.g. "Kata").
        text: What they said.
        role: Optional role for this speaker (e.g. "Product Manager"). Registered
            for the rest of the session; if omitted, a previously registered or the
            default role is used.
        session_id: Which dispute this belongs to.

    Returns the mediator's reply, or a note if the mediator is waiting for the other
    side before speaking.
    """
    session = _session(session_id)
    if not session.active:
        return "No active mediation. Call start_mediation(topic) first."

    if role:
        _register_participant(speaker, role)

    resolved_role = _engine.config.get("default_role", "Participant")
    for p in (_engine.config.get("participants") or {}).values():
        if p["name"].lower() == speaker.lower():
            resolved_role = p["role"]
            break

    session.add_message(speaker, resolved_role, text)

    from .commands import both_sides_spoke_since_last_mediator

    if both_sides_spoke_since_last_mediator(session):
        return _engine.respond(session)
    return (
        f"Recorded {speaker}'s statement. The mediator is waiting for the other "
        "party to respond before it speaks. Add the next statement, or call "
        "request_decision() to force the mediator to act now."
    )


@mcp.tool()
def request_decision(session_id: str = "default") -> str:
    """Force the mediator to make its recommendation now.

    Uncertainties are flagged in the DISPUTED FACTS / ESCALATION sections. The
    recommendation still requires human approval.
    """
    session = _session(session_id)
    if not session.active:
        return "No active mediation. Call start_mediation(topic) first."
    warning = ""
    if not session.decision_allowed():
        warning = (
            "[Note: not every party has spoken at least twice; this is a forced "
            "decision and uncertainties are flagged.]\n\n"
        )
    return warning + _engine.respond(session, force_decision=True)


@mcp.tool()
def mediation_status(session_id: str = "default") -> str:
    """Report who has spoken and where the dispute stands."""
    session = _session(session_id)
    spoke = ", ".join(sorted(session.speakers())) or "nobody yet"
    return (
        f"Session: {session_id}\n"
        f"Topic: {session.topic or '—'}\n"
        f"Active: {session.active} | Decided: {session.decided}\n"
        f"Decision allowed by protocol: {session.decision_allowed()}\n"
        f"Spoke so far: {spoke}\n"
        f"Messages: {len(session.messages)}"
    )


@mcp.tool()
def reset_mediation(session_id: str = "default") -> str:
    """Clear a mediation session."""
    _session(session_id).reset()
    return f"Session '{session_id}' cleared."


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
