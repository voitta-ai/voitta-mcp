"""Read-only HighLevel CRM MCP server.

Every HTTP call goes through _get(), which only issues GET requests, so no
tool can create, update or delete CRM data.
"""

import os

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

BASE_URL = "https://services.leadconnectorhq.com"
API_VERSION = "2021-07-28"
# Cloudflare rejects Python's default User-Agent with 403 "Error 1010".
USER_AGENT = "curl/8.7.1"

HOST = os.environ.get("CRM_HIGHLEVEL_HOST", "127.0.0.1")
PORT = int(os.environ.get("CRM_HIGHLEVEL_PORT", "8811"))
# Web app host used to build links to CRM records (white-label domain or app.gohighlevel.com).
APP_URL = os.environ.get("CRM_HIGHLEVEL_APP_URL", "https://crm.ctox.com")

mcp = MCPServer("crm-highlevel")
READ_ONLY = ToolAnnotations(read_only_hint=True)


def _location_id() -> str:
    retval = os.environ["CRM_CTOX_LOCATION_ID"]
    return retval


def _get(path: str, params: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {os.environ['CRM_CTOX_TOKEN']}",
        "Version": API_VERSION,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    response = httpx.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)
    if response.status_code >= 400:
        # Body only; the request (and its Authorization header) is never surfaced.
        raise RuntimeError(f"HighLevel GET {path} failed: {response.status_code} {response.text[:300]}")
    retval = response.json()
    return retval


def _stage_names() -> dict:
    data = _get("/opportunities/pipelines", {"locationId": _location_id()})
    retval = {
        stage["id"]: (pipeline["name"], stage["name"])
        for pipeline in data.get("pipelines", [])
        for stage in pipeline.get("stages", [])
    }
    return retval


@mcp.tool(annotations=READ_ONLY)
def crm_find_contact(query: str) -> list[dict]:
    """Look up accounts in the CRM by company or person name. Returns the current contact record: id, name, company, email, tags and a link to the record in the CRM."""
    data = _get("/contacts/", {"locationId": _location_id(), "query": query, "limit": 20})
    retval = [
        {
            "id": c.get("id"),
            "name": c.get("contactName"),
            "company": c.get("companyName"),
            "email": c.get("email"),
            "tags": c.get("tags", []),
            "url": f"{APP_URL}/v2/location/{_location_id()}/contacts/detail/{c.get('id')}",
        }
        for c in data.get("contacts", [])
    ]
    return retval


@mcp.tool(annotations=READ_ONLY)
def crm_get_opportunities(contact_id: str) -> list[dict]:
    """Current state of a contact's deals in the CRM: pipeline, stage, status (open/won/lost/abandoned) and monetary value."""
    data = _get("/opportunities/search", {"location_id": _location_id(), "contact_id": contact_id})
    stages = _stage_names()
    retval = [
        {
            "id": o.get("id"),
            "name": o.get("name"),
            "pipeline": stages.get(o.get("pipelineStageId"), (None, None))[0],
            "stage": stages.get(o.get("pipelineStageId"), (None, None))[1],
            "status": o.get("status"),
            "monetary_value": o.get("monetaryValue"),
        }
        for o in data.get("opportunities", [])
    ]
    return retval


@mcp.tool(annotations=READ_ONLY)
def crm_get_notes(contact_id: str) -> list[dict]:
    """Short CRM notes currently attached to a contact record."""
    data = _get(f"/contacts/{contact_id}/notes")
    retval = [
        {"id": n.get("id"), "body": n.get("bodyText") or n.get("body"), "date_added": n.get("dateAdded")}
        for n in data.get("notes", [])
    ]
    return retval


@mcp.tool(annotations=READ_ONLY)
def crm_list_pipelines() -> list[dict]:
    """The CRM's deal pipelines and their stage names, in order."""
    data = _get("/opportunities/pipelines", {"locationId": _location_id()})
    retval = [
        {"id": p.get("id"), "name": p.get("name"), "stages": [s.get("name") for s in p.get("stages", [])]}
        for p in data.get("pipelines", [])
    ]
    return retval


def main() -> None:
    for name in ("CRM_CTOX_TOKEN", "CRM_CTOX_LOCATION_ID"):
        if not os.environ.get(name):
            raise SystemExit(f"{name} is not set")
    mcp.run(transport="streamable-http", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
