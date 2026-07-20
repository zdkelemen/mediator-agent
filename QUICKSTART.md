# Quick Start

The fastest path from zero to a running mediation. Pick a **provider** (the LLM
brain) and a **surface** (how people talk to it). Works on Windows, macOS, Linux
with Python 3.10+.

Command boxes show bash first, then the PowerShell equivalent where it differs.

---

## 0. Install (30 seconds)

```bash
pip install -e ".[all]"          # everything; or pick extras: .[openai] .[slack] .[mcp] .[webhook] .[teams]
cp .env.example .env             # PowerShell: Copy-Item .env.example .env
```

---

## 1. Pick a provider (the LLM)

### Option A — Claude (default)

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
```

`config.yaml` already has `provider: anthropic` and `model: claude-opus-4-8`. Done.

### Option B — OpenAI

```bash
export MEDIATOR_PROVIDER=openai
export OPENAI_API_KEY=sk-...
```

Set `model: gpt-4o` (or your model) in `config.yaml`.

### Option C — Ollama (fully local, no cloud, no key)

```bash
# install Ollama from https://ollama.com, then:
ollama pull llama3.1

export MEDIATOR_PROVIDER=ollama            # PowerShell: $env:MEDIATOR_PROVIDER="ollama"
```

Set `provider: ollama` and `model: llama3.1` in `config.yaml`. The mediator will
talk to your local Ollama at `http://localhost:11434/v1` — nothing leaves the machine.

For **Azure OpenAI / LM Studio / OpenRouter / vLLM**: use Option B and add
`OPENAI_BASE_URL=<that endpoint>`.

---

## 2. Pick a surface (how people talk to it)

### CLI — try it right now (2 minutes)

```bash
python -m mediator.cli
```

```
Dispute topic: Ship Feature X in Q3 vs. refactor the payment module
> kata: Feature X has to ship in Q3, it's a contractual OEM commitment.
> gabor: The payment module can't handle it — refactor first.
> kata: The OEM penalty clause is bigger than the tech-debt cost.
> gabor: Fine, but only with a hard Q4 refactor commitment.
> /decide
```

Commands: `/decide`, `/reset`, `/exit`.

### Any agentic CLI (Claude Code, Codex, Cursor…) via MCP

```bash
claude mcp add mediator -- python -m mediator.mcp_server
```

Then, inside that CLI, drive it with the tools `start_mediation`, `add_statement`,
`request_decision`, `mediation_status`, `reset_mediation`.

### Generic webhook (no Azure Bot; works for Teams via Workflows, and anything HTTP)

```bash
python -m mediator.adapters.webhook_app        # listens on :3979
```

```bash
curl -X POST http://localhost:3979/message -H "Content-Type: application/json" \
  -d '{"channel_id":"team-42","user_id":"u1","name":"Kata","text":"start Ship X vs refactor"}'
```

Response: `{"replies": [...]}`. Set `MEDIATOR_WEBHOOK_TOKEN` to require an
`X-Mediator-Token` header.

### Slack

1. Create an app at https://api.slack.com/apps (From scratch).
2. **Socket Mode** on → App-Level Token with `connections:write` → `SLACK_APP_TOKEN` (xapp-).
3. **OAuth & Permissions** → scopes `chat:write`, `channels:history`, `groups:history`, `users:read` → Install → `SLACK_BOT_TOKEN` (xoxb-).
4. **Event Subscriptions** → bot events `message.channels`, `message.groups`.
5. Fill `participants` in `config.yaml` with Slack user IDs.
6. Run and invite:

```bash
export SLACK_BOT_TOKEN=xoxb-... SLACK_APP_TOKEN=xapp-...
python -m mediator.adapters.slack_app
# in Slack: /invite @Mediator
```

### Microsoft Teams

Easiest is **no Azure Bot**: run the webhook adapter above and add a Teams
**Workflows / Power Automate** flow (trigger on a new channel message → HTTP POST to
`/message` → post the `replies` back). If you already run an Azure Bot resource, use
`python -m mediator.adapters.teams_app` with `MICROSOFT_APP_ID` / `MICROSOFT_APP_PASSWORD`.

---

## 3. Chat commands (Slack / Teams / webhook)

| Command | Effect |
|---|---|
| `@Mediator start <topic>` | Start a new dispute |
| `@Mediator decide` | Request a decision (approve with ✅ / ❌) |
| `@Mediator status` | Who has spoken, where it stands |
| `@Mediator reset` | Clear the session |

---

## 4. Make it yours

Edit `config.yaml`:

- **criteria** — the decision criteria and weights. This is the governance core: the
  decision is auditable because *your org* set the weighting, not the model.
- **participants** — map platform user IDs to names + roles (PM, Architect, …).
- **provider / model / max_tokens** — the LLM backend.

Tone, protocol, and the decision format live in `mediator/prompts.py`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Unknown provider '…'` | `provider:` must be `anthropic`, `openai`, or `ollama`. |
| Ollama: connection refused | Is Ollama running? `ollama serve`. Pulled the model? `ollama pull <model>`. |
| Ollama: model not found | `model:` in `config.yaml` must match a pulled model (`ollama list`). |
| Missing API key error | Export the key for your provider (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`). |
| Slack won't connect | Socket Mode enabled? Both `xoxb-` and `xapp-` tokens set? |
| Mediator won't decide | By design — every party must speak twice, or use `decide` to force it. |

Full docs: [README](README.md).
