# Mediator Agent

An impartial AI mediator for disputes between product managers and architects.
It talks to several parties at once in a shared session — on **Slack**, in
**Microsoft Teams**, on the **CLI**, or from inside **any agentic CLI** (Claude
Code, Codex, Cursor, …) over **MCP**. It follows a structured protocol to separate
positions from interests and makes an **auditable recommendation** weighed against
**your organization's recorded criteria** — with human approval.

## How it works

1. **Exploration** – separate positions from the underlying interests, ask targeted questions
2. **Facts** – request missing/disputed facts (effort, deadline, tech debt, A-SPICE impact)
3. **Steelman** – restate both sides in their strongest form, with the parties' confirmation
4. **Decision** – fixed format: DECISION / RATIONALE / CONDITIONS / DISPUTED FACTS / ESCALATION

There is a code-level guard too: the engine won't allow a final decision until every
party has spoken at least twice (position + reaction) — unless the parties explicitly
ask (the `decide` command), in which case the uncertainty stays flagged.

## Install

```bash
pip install -e .            # base engine + CLI
pip install -e ".[slack]"   # + Slack adapter
pip install -e ".[teams]"   # + Microsoft Teams adapter
pip install -e ".[mcp]"     # + MCP server for agentic CLIs
pip install -e ".[all]"     # everything

cp .env.example .env        # fill in your keys
```

Everything is configured in `config.yaml`; secrets go in `.env` (see `.env.example`).

## 1. Try it on the CLI (no chat platform, ~2 min)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m mediator.cli
```

```
Dispute topic: Ship Feature X in Q3 vs. refactor the payment module
> kata: Feature X has to ship in Q3, it's a contractual OEM commitment.
> gabor: In its current state the payment module can't handle it — refactor first.
...
> /decide
```

Commands: `/decide`, `/reset`, `/exit`.

## 2. Use it from any agentic CLI (MCP)

The mediator ships as an **MCP server**, so Claude Code, Codex, Cursor, Windsurf and
other MCP-speaking CLIs can drive it directly. The governance core (criteria,
protocol, human-in-the-loop) is identical no matter which CLI is at the wheel.

Register with Claude Code:

```bash
claude mcp add mediator -- python -m mediator.mcp_server
```

Or in an MCP client config (Codex, Cursor, …):

```json
{
  "mcpServers": {
    "mediator": {
      "command": "python",
      "args": ["-m", "mediator.mcp_server"],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-...", "MEDIATOR_CONFIG": "config.yaml" }
    }
  }
}
```

Exposed tools: `start_mediation`, `add_statement`, `request_decision`,
`mediation_status`, `reset_mediation` (each takes an optional `session_id` so you
can run several disputes in parallel).

## 3. Deploy the Slack bot

1. https://api.slack.com/apps → **Create New App** → From scratch
2. **Socket Mode** → enable, generate an App-Level Token with the `connections:write`
   scope → this is `SLACK_APP_TOKEN` (xapp-)
3. **OAuth & Permissions** → Bot Token Scopes: `chat:write`, `channels:history`,
   `groups:history`, `users:read` → Install to Workspace → `SLACK_BOT_TOKEN` (xoxb-)
4. **Event Subscriptions** → bot events: `message.channels`, `message.groups`
5. Fill the `participants` section of `config.yaml` with the Slack user IDs
   (profile → ⋮ → Copy member ID)
6. Start it:

```bash
python -m mediator.adapters.slack_app
```

7. Invite the bot to the channel: `/invite @Mediator`

## 4. Deploy the Microsoft Teams bot

1. In Azure, create an **Azure Bot** resource; note its **Microsoft App ID** and
   create a client secret → `MICROSOFT_APP_ID` / `MICROSOFT_APP_PASSWORD`
2. Set the bot's **messaging endpoint** to `https://<your-host>/api/messages`
   (use a tunnel such as *dev tunnels* or ngrok during development)
3. Add the **Teams channel** to the bot, then sideload/install the app in Teams
4. Optionally map Teams users to roles in `config.yaml` (key = the user's Azure AD
   object id, from the activity's `from.aadObjectId`)
5. Start it:

```bash
python -m mediator.adapters.teams_app
```

The bot listens on `http://localhost:$PORT/api/messages` (default port `3978`).

### Chat commands (Slack & Teams)

| Command | Effect |
|---|---|
| `@Mediator start <topic>` | Start a new dispute |
| `@Mediator decide` | Request a decision (approve with ✅/❌ reactions) |
| `@Mediator status` | Who has spoken, where the dispute stands |
| `@Mediator reset` | Clear the session |

The mediator doesn't reply to every message: it speaks when mentioned, or once both
parties have responded since its last turn — so it doesn't talk over anyone. In a
Teams 1:1 chat every message is treated as addressed to the bot.

## Customization

Everything is in `config.yaml`:

- **criteria** – the decision criteria and their weights. This is the governance core:
  the decision is auditable because the organization, not the model, fixed the weighting.
- **participants** – platform user ID → name + role
- **model / max_tokens** – API parameters

The mediator's behaviour (protocol, tone, decision format) lives in `mediator/prompts.py`.

## Architecture

```
Slack channel ───┐
Microsoft Teams ─┤
Agentic CLI (MCP)┤─► commands.py (shared protocol) ─► session.py (state, guards, JSON)
CLI ─────────────┘                                          │
                                                            ▼
                                                     engine.py (Claude API, system prompt + history)
                                                            │
                                                            ▼
                                                     prompts.py (mediation protocol, criteria)
```

- `mediator/commands.py` — platform-agnostic command + turn logic shared by every adapter
- `mediator/adapters/` — `slack_app.py`, `teams_app.py`
- `mediator/mcp_server.py` — MCP server for agentic CLIs
- `mediator/cli.py` — interactive local CLI

Session state persists in `state/` across restarts.

## Possible next steps

- **Jira/Confluence fact-checking** via MCP (effort, capacity, roadmap)
- **Advocate sub-agents** – separate agents reinforcing the PM and architect
  perspectives, with the mediator judging over them
- **Decision log** exported to Confluence (audit trail for A-SPICE)
```
