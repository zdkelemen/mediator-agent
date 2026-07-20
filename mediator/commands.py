"""Platform-agnostic command handling shared by every chat adapter.

An adapter only has to (1) detect whether the bot was mentioned, (2) hand us the
speaker's platform user id + display name and the message text, and (3) send back
whatever strings we return. All the mediation protocol lives here, so Slack and
Teams behave identically.
"""

from .engine import MediatorEngine
from .session import Session, MEDIATOR_ROLE

# Command keywords (matched case-insensitively at the start of a mention).
CMD_START = "start"
CMD_RESET = "reset"
CMD_STATUS = "status"
CMD_DECIDE = "decide"

START_BANNER = (
    ":scales: *Mediation started.* Topic: _{topic}_\n"
    "Each party, please first describe your *position and the interest behind it*. "
    "I will ask questions, summarize, and make a recommendation against the recorded "
    "criteria. Request a decision with the `@Mediator decide` command."
)

DECIDE_APPROVAL = (
    "\n\n:ballot_box_with_check: *Approval:* react with :white_check_mark: / :x:. "
    "The decision becomes valid only with human approval."
)

NO_ACTIVE = "No active dispute. Start one: `@Mediator start <topic>`"

FORCE_WARNING = (
    ":warning: Not every party has spoken at least twice yet (position + reaction). "
    "I will produce a forced decision, but I will flag the uncertainties."
)


def both_sides_spoke_since_last_mediator(session: Session) -> bool:
    speakers_since = set()
    for m in reversed(session.messages):
        if m["role"] == MEDIATOR_ROLE:
            break
        speakers_since.add(m["speaker"])
    return len(speakers_since) >= 2


def handle_command(
    engine: MediatorEngine,
    session: Session,
    command_text: str,
) -> list[str] | None:
    """Handle an explicit @mention command. Returns reply strings, or None if the
    text was not a recognized command (so it should be treated as a normal message)."""
    lower = command_text.lower()

    if lower.startswith(CMD_START):
        session.reset()
        session.topic = command_text[len(CMD_START):].strip() or "(not provided)"
        session.active = True
        session.save()
        return [START_BANNER.format(topic=session.topic)]

    if lower.startswith(CMD_RESET):
        session.reset()
        return [":wastebasket: Session cleared."]

    if lower.startswith(CMD_STATUS):
        spoke = ", ".join(sorted(session.speakers())) or "nobody yet"
        return [
            f"Topic: _{session.topic or '—'}_ | Active: {session.active} | "
            f"Decided: {session.decided} | Spoke: {spoke}"
        ]

    if lower.startswith(CMD_DECIDE) or lower.startswith("decision"):
        if not session.active:
            return [NO_ACTIVE]
        replies = []
        if not session.decision_allowed():
            replies.append(FORCE_WARNING)
        reply = engine.respond(session, force_decision=True)
        replies.append(reply + DECIDE_APPROVAL)
        return replies

    return None


def handle_participant_message(
    engine: MediatorEngine,
    session: Session,
    *,
    user_id: str,
    fallback_name: str,
    text: str,
    mentioned: bool,
) -> list[str]:
    """Record a normal dispute message and decide whether the mediator speaks."""
    if not session.active:
        return [NO_ACTIVE] if mentioned else []

    name, role = engine.resolve_participant(user_id, fallback_name=fallback_name)
    session.add_message(name, role, text)

    # The mediator speaks when addressed directly, or once both sides have
    # spoken since its last turn — so it doesn't talk over the parties.
    if mentioned or both_sides_spoke_since_last_mediator(session):
        return [engine.respond(session)]
    return []
