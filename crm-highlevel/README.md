# crm-highlevel

MCP server for a HighLevel (LeadConnector) CRM location. It exposes the
current state of contacts and deals. It is read-only by default: the read
tools go through a single GET-only helper (`_get` in
`src/crm_highlevel/server.py`), and no tool can create, update or delete
anything.

One narrow write tool, `crm_update_opportunity_status`, exists only when
`CRM_HIGHLEVEL_ENABLE_WRITES=1`. It changes one opportunity's stage and/or
status and nothing else; there are no delete, contact-edit or generic write
tools. Clients should treat it as a mutation that needs human approval.

## Tools

The read tools are marked `readOnlyHint: true`.

| Tool | Arguments | Returns |
|---|---|---|
| `crm_find_contact` | `query` (company or person name) | id, name, company, email, tags, url (link to the record in the CRM web app) |
| `crm_get_opportunities` | `contact_id` | pipeline, stage, status, monetary value |
| `crm_get_notes` | `contact_id` | note id, body, date added |
| `crm_list_pipelines` | none | pipelines and their stage names, in order |

Write tool, registered only with `CRM_HIGHLEVEL_ENABLE_WRITES=1`
(`readOnlyHint: false`, `destructiveHint: true`):

| Tool | Arguments | Returns |
|---|---|---|
| `crm_update_opportunity_status` | `opportunity_id`, `stage` (stage name in the deal's current pipeline) and/or `status` (`open`, `won`, `lost`, `abandoned`) | the updated deal, same shape as `crm_get_opportunities` |

## Configuration

Read from the environment of the process that runs the server:

| Variable | Required | Meaning |
|---|---|---|
| `CRM_CTOX_TOKEN` | yes | HighLevel Private Integration Token (bearer). Never logged. |
| `CRM_CTOX_LOCATION_ID` | yes | HighLevel location (sub-account) ID |
| `CRM_HIGHLEVEL_HOST` | no | Bind address, default `127.0.0.1` |
| `CRM_HIGHLEVEL_PORT` | no | Port, default `8811` |
| `CRM_HIGHLEVEL_ENABLE_WRITES` | no | `1` registers `crm_update_opportunity_status`; anything else (default) keeps the server read-only |
| `CRM_HIGHLEVEL_APP_URL` | no | CRM web app base for record links, default `https://crm.ctox.com` (use `https://app.gohighlevel.com` for a non-white-label account) |

The operator keeps `CRM_CTOX_TOKEN` and `CRM_CTOX_LOCATION_ID` in
`~/.bash_profile_manda`; any other mechanism that puts them in the
environment works the same.

## Running

### Docker (default)

Requires Docker with Compose. From `crm-highlevel/`:

```bash
source ~/.bash_profile_manda && docker compose up -d --build
```

To run with the write tool enabled:

```bash
source ~/.bash_profile_manda && CRM_HIGHLEVEL_ENABLE_WRITES=1 docker compose up -d --build
```

Compose reads `CRM_CTOX_TOKEN` and `CRM_CTOX_LOCATION_ID` from the shell at
`up` time and refuses to start if either is missing. The container runs with
`restart: unless-stopped`, so it comes back after a reboot as long as the
Docker engine starts at login (Docker Desktop: Settings > General > "Start
Docker Desktop when you sign in"). Re-run the command after changing the
token or the code.

The port is published on `127.0.0.1` only, never on other interfaces.

**Token visibility:** the token is stored in the container's configuration,
so anyone who can run `docker inspect` on this machine can read it.

### Without Docker

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
cd crm-highlevel
uv venv .venv
uv pip install -e .
source ~/.bash_profile_manda   # exports CRM_CTOX_TOKEN, CRM_CTOX_LOCATION_ID
.venv/bin/crm-highlevel
```

### Endpoint

Either way, the server speaks MCP over streamable HTTP at:

```
http://127.0.0.1:8811/mcp
```

## HighLevel API notes

- Base URL `https://services.leadconnectorhq.com`, header `Version: 2021-07-28`.
- Cloudflare returns 403 "Error 1010" for Python's default User-Agent, so the
  server sends a curl User-Agent.
- A valid token without `locationId` returns 422; an invalid token returns 401
  "Invalid Private Integration token".
- Opportunity search takes `location_id` and `contact_id` (snake case); the
  contacts and pipelines endpoints take `locationId`.
