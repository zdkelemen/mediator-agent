# Mediator Agent

An impartial AI mediator for disputes between product managers and architects.
It talks to several parties at once in a shared session — on **Slack**, in
**Microsoft Teams**, on the **CLI**, through a **generic webhook**, or from inside
**any agentic CLI** (Claude Code, Codex, Cursor, …) over **MCP**. It follows a
structured protocol to separate positions from interests and makes an **auditable
recommendation** weighed against **your organization's recorded criteria** — with
human approval.

It is **vendor-independent** (Claude, OpenAI, or any OpenAI-compatible endpoint),
**OS-independent** (Windows, macOS, Linux), and needs **no Azure Bot** for Teams.

## How it works

1. **Exploration** – separate positions from the underlying interests, ask targeted questions
2. **Facts** – request missing/disputed facts (effort, deadline, tech debt, A-SPICE impact)
3. **Steelman** – restate both sides in their strongest form, with the parties' confirmation
4. **Decision** – fixed format: DECISION / RATIONALE / CONDITIONS / DISPUTED FACTS / ESCALATION

There is a code-level guard too: the engine won't allow a final decision until every
party has spoken at least twice (position + reaction) — unless the parties explicitly
ask (the `decide` command), in which case the uncertainty stays flagged.

## Install

Works on Windows, macOS, and Linux (Python 3.10+).

```bash
pip install -e .            # base engine + CLI + Claude provider
pip install -e ".[openai]"  # + OpenAI / OpenAI-compatible provider
pip install -e ".[slack]"   # + Slack adapter
pip install -e ".[teams]"   # + Microsoft Teams (Bot Framework) adapter
pip install -e ".[webhook]" # + generic HTTP webhook adapter (no Azure Bot)
pip install -e ".[mcp]"     # + MCP server for agentic CLIs
pip install -e ".[all]"     # everything
```

Copy `.env.example` to `.env` and fill in the keys you need. On PowerShell:
`Copy-Item .env.example .env`. On bash: `cp .env.example .env`.

## Choosing an LLM provider (vendor-independent)

The mediator's reasoning is decoupled from any single vendor. Pick a backend in
`config.yaml` (`provider:`) or with the `MEDIATOR_PROVIDER` env var:

| Provider | Set | Needs | Notes |
|---|---|---|---|
| `anthropic` | default | `ANTHROPIC_API_KEY` | Claude via the Anthropic SDK |
| `openai` | `provider: openai` | `OPENAI_API_KEY` | OpenAI **or** any OpenAI-compatible API |

For a self-hosted or third-party OpenAI-compatible endpoint (Azure OpenAI, Ollama,
LM Studio, OpenRouter, vLLM, Together, …), set `OPENAI_BASE_URL`, e.g. Ollama:

```bash
export MEDIATOR_PROVIDER=openai
export OPENAI_API_KEY=ollama            # any non-empty value for local servers
export OPENAI_BASE_URL=http://localhost:11434/v1
# and set the model in config.yaml, e.g.  model: llama3.1
```

## 1. Try it on the CLI (~2 min)

```bash
# bash:        export ANTHROPIC_API_KEY=sk-ant-...
# PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."
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
other MCP-speaking CLIs can drive it directly.

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
`mediation_status`, `reset_mediation` (each takes an optional `session_id`).

## 3. Generic webhook (no Azure Bot, any platform)

The webhook adapter is the platform-neutral surface: a tiny HTTP server that takes a
message as JSON and returns the mediator's replies as JSON. **This is how you run the
mediator in Microsoft Teams without an Azure Bot resource** — build a Teams flow in
Power Automate / Workflows (trigger on a new channel message → HTTP POST here → post
the replies back). The same endpoint works for Slack/Discord/Mattermost bridges, cron
jobs, or your own app.

```bash
python -m mediator.adapters.webhook_app     # listens on $PORT (default 3979)
```

```bash
curl -X POST http://localhost:3979/message \
  -H "Content-Type: application/json" \
  -d '{"channel_id":"team-42","user_id":"u1","name":"Kata","text":"start Ship X vs refactor"}'
```

Request fields: `channel_id`, `user_id`, `text` (required); `name`, `mentioned`
(optional). Response: `{"replies": [...]}`. Set `MEDIATOR_WEBHOOK_TOKEN` to require an
`X-Mediator-Token` header.

## 4. Slack bot

1. https://api.slack.com/apps → **Create New App** → From scratch
2. **Socket Mode** → enable, generate an App-Level Token with `connections:write` → `SLACK_APP_TOKEN` (xapp-)
3. **OAuth & Permissions** → Bot Token Scopes: `chat:write`, `channels:history`, `groups:history`, `users:read` → Install → `SLACK_BOT_TOKEN` (xoxb-)
4. **Event Subscriptions** → bot events: `message.channels`, `message.groups`
5. Fill `participants` in `config.yaml` with Slack user IDs (profile → ⋮ → Copy member ID)
6. `python -m mediator.adapters.slack_app`
7. Invite the bot: `/invite @Mediator`

## 5. Microsoft Teams

Two options:

- **Webhook (recommended, no Azure Bot)** — use the generic webhook adapter above
  with a Teams Workflow/Power Automate flow. Nothing to register in Azure.
- **Bot Framework adapter** (`mediator/adapters/teams_app.py`, the `[teams]` extra) —
  if you *do* run an Azure Bot resource: set the messaging endpoint to
  `https://<host>/api/messages`, fill `MICROSOFT_APP_ID` / `MICROSOFT_APP_PASSWORD`,
  then `python -m mediator.adapters.teams_app`.

### Chat commands (Slack, Teams, webhook)

| Command | Effect |
|---|---|
| `@Mediator start <topic>` | Start a new dispute |
| `@Mediator decide` | Request a decision (approve with ✅/❌ reactions) |
| `@Mediator status` | Who has spoken, where the dispute stands |
| `@Mediator reset` | Clear the session |

The mediator doesn't reply to every message: it speaks when addressed, or once both
parties have responded since its last turn — so it doesn't talk over anyone.

## Customization

Everything is in `config.yaml`:

- **provider / model / max_tokens** – which LLM backend and model to use
- **criteria** – the decision criteria and their weights (the auditable governance core)
- **participants** – platform user ID → name + role

The mediator's behaviour (protocol, tone, decision format) lives in `mediator/prompts.py`.

## Architecture

```
Slack ───────────┐
Microsoft Teams ─┤
Webhook (any) ───┤─► commands.py (shared protocol) ─► session.py (state, guards, JSON)
Agentic CLI (MCP)┤                                          │
CLI ─────────────┘                                          ▼
                                                     engine.py (protocol enforcement)
                                                            │
                                            ┌───────────────┴───────────────┐
                                            ▼                               ▼
                                     prompts.py (protocol,          llm.py (provider layer:
                                     criteria)                      Anthropic | OpenAI-compatible)
```

- `mediator/llm.py` — vendor-independent provider layer (Claude, OpenAI-compatible)
- `mediator/commands.py` — platform-agnostic command + turn logic shared by every adapter
- `mediator/adapters/` — `slack_app.py`, `teams_app.py`, `webhook_app.py`
- `mediator/mcp_server.py` — MCP server for agentic CLIs
- `mediator/cli.py` — interactive local CLI

Session state persists in `state/` across restarts (filenames are slugified, so any
platform's channel/conversation IDs are safe on any OS).

## Possible next steps

- **Jira/Confluence fact-checking** via MCP (effort, capacity, roadmap)
- **Advocate sub-agents** – separate agents reinforcing the PM and architect perspectives
- **Decision log** exported to Confluence (audit trail for A-SPICE)
```
