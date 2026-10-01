# crm-highlevel

Read-only MCP server for a HighLevel (LeadConnector) CRM location. It exposes
the current state of contacts and deals; it has no tool that can create,
update or delete anything. Every API call goes through a single GET-only
helper (`_get` in `src/crm_highlevel/server.py`), so read-only is a property
of the code, not of configuration.

## Tools

All tools are read-only (`readOnlyHint: true`).

| Tool | Arguments | Returns |
|---|---|---|
| `crm_find_contact` | `query` (company or person name) | id, name, company, email, tags |
| `crm_get_opportunities` | `contact_id` | pipeline, stage, status, monetary value |
| `crm_get_notes` | `contact_id` | note id, body, date added |
| `crm_list_pipelines` | none | pipelines and their stage names, in order |

## Configuration

Read from the environment of the process that runs the server:

| Variable | Required | Meaning |
|---|---|---|
| `CRM_CTOX_TOKEN` | yes | HighLevel Private Integration Token (bearer). Never logged. |
| `CRM_CTOX_LOCATION_ID` | yes | HighLevel location (sub-account) ID |
| `CRM_HIGHLEVEL_HOST` | no | Bind address, default `127.0.0.1` |
| `CRM_HIGHLEVEL_PORT` | no | Port, default `8811` |

The operator keeps `CRM_CTOX_TOKEN` and `CRM_CTOX_LOCATION_ID` in
`~/.bash_profile_manda`; any other mechanism that puts them in the
environment works the same.

## Running

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
cd crm-highlevel
uv venv .venv
uv pip install -e .
source ~/.bash_profile_manda   # exports CRM_CTOX_TOKEN, CRM_CTOX_LOCATION_ID
.venv/bin/crm-highlevel
```

The server speaks MCP over streamable HTTP at:

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
