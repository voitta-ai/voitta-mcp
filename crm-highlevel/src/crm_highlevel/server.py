"""HighLevel CRM MCP server, read-only by default.

The read tools go through _get(), which only issues GET requests. The single
write tool, crm_update_opportunity_status, is registered only when
CRM_HIGHLEVEL_ENABLE_WRITES=1; it is the only caller of _put() and can change
nothing but one opportunity's stage and status. Without the flag no tool can
create, update or delete CRM data.
"""

import os

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

BASE_URL = "https://services.leadconnectorhq.com"
API_VERSION = "2021-07-28"
# Cloudflare rejects Python's default User-Agent with 403 "Error 1010".
USER_AGENT = "curl/8.7.1"

HOST = os.environ.get("CRM_HIGHLEVEL_HOST", "127.0.0.1")
PORT = int(os.environ.get("CRM_HIGHLEVEL_PORT", "8811"))
# Web app host used to build links to CRM records (white-label domain or app.gohighlevel.com).
APP_URL = os.environ.get("CRM_HIGHLEVEL_APP_URL", "https://crm.ctox.com")
WRITES_ENABLED = os.environ.get("CRM_HIGHLEVEL_ENABLE_WRITES") == "1"
OPPORTUNITY_STATUSES = ("open", "won", "lost", "abandoned")
PAGE_SIZE = 100

mcp = MCPServer("crm-highlevel")
READ_ONLY = ToolAnnotations(read_only_hint=True)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True)


def _location_id() -> str:
    retval = os.environ["CRM_CTOX_LOCATION_ID"]
    return retval


def _headers() -> dict:
    retval = {
        "Authorization": f"Bearer {os.environ['CRM_CTOX_TOKEN']}",
        "Version": API_VERSION,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    return retval


def _get(path: str, params: dict | None = None) -> dict:
    response = httpx.get(f"{BASE_URL}{path}", params=params, headers=_headers(), timeout=30)
    if response.status_code >= 400:
        # Body only; the request (and its Authorization header) is never surfaced.
        raise RuntimeError(f"HighLevel GET {path} failed: {response.status_code} {response.text[:300]}")
    retval = response.json()
    return retval


def _contact_url(contact_id: str | None) -> str:
    retval = f"{APP_URL}/v2/location/{_location_id()}/contacts/detail/{contact_id}"
    return retval


def _put(path: str, body: dict) -> dict:
    response = httpx.put(f"{BASE_URL}{path}", json=body, headers=_headers(), timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(f"HighLevel PUT {path} failed: {response.status_code} {response.text[:300]}")
    retval = response.json()
    return retval


def _opportunity_view(o: dict, stages: dict) -> dict:
    retval = {
        "id": o.get("id"),
        "name": o.get("name"),
        "pipeline": stages.get(o.get("pipelineStageId"), (None, None))[0],
        "stage": stages.get(o.get("pipelineStageId"), (None, None))[1],
        "status": o.get("status"),
        "monetary_value": o.get("monetaryValue"),
    }
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
            "url": _contact_url(c.get("id")),
        }
        for c in data.get("contacts", [])
    ]
    return retval


@mcp.tool(annotations=READ_ONLY)
def crm_get_opportunities(contact_id: str) -> list[dict]:
    """Current state of a contact's deals in the CRM: pipeline, stage, status (open/won/lost/abandoned) and monetary value."""
    data = _get("/opportunities/search", {"location_id": _location_id(), "contact_id": contact_id})
    stages = _stage_names()
    retval = [_opportunity_view(o, stages) for o in data.get("opportunities", [])]
    return retval


@mcp.tool(annotations=READ_ONLY)
def crm_list_opportunities(status: str | None = None, stage: str | None = None, limit: int = 10) -> list[dict]:
    """Current deals across the whole CRM, highest monetary value first. Filter by status (open, won, lost, abandoned; "won" deals are customers) and/or stage name. Each row has the deal, company, contact, pipeline, stage, status, value and a link to the contact record in the CRM."""
    if status is not None and status not in OPPORTUNITY_STATUSES:
        raise ToolError(f"status must be one of {', '.join(OPPORTUNITY_STATUSES)}")
    params = {"location_id": _location_id(), "limit": PAGE_SIZE}
    if status is not None:
        params["status"] = status
    # HighLevel's search cannot sort, so fetch every page and rank here.
    deals = []
    page = 1
    while page:
        data = _get("/opportunities/search", {**params, "page": page})
        deals.extend(data.get("opportunities", []))
        page = data.get("meta", {}).get("nextPage") or None
    stages = _stage_names()
    if stage is not None:
        deals = [o for o in deals if (stages.get(o.get("pipelineStageId"), (None, ""))[1] or "").lower() == stage.lower()]
    # Highest value first; ties break by deal name so the order is stable.
    deals.sort(key=lambda o: (-(o.get("monetaryValue") or 0), o.get("name") or ""))
    retval = [
        {
            **_opportunity_view(o, stages),
            "company": (o.get("contact") or {}).get("companyName"),
            "contact": (o.get("contact") or {}).get("name"),
            "url": _contact_url((o.get("contact") or {}).get("id")),
        }
        for o in deals[: max(1, limit)]
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


def crm_update_opportunity_status(opportunity_id: str, stage: str | None = None, status: str | None = None) -> dict:
    """Change one deal's pipeline stage and/or status in the CRM. stage is a stage name within the deal's current pipeline; status is one of open, won, lost, abandoned. Changes nothing else. Returns the deal as updated."""
    if stage is None and status is None:
        raise ToolError("Give stage, status, or both")
    if status is not None and status not in OPPORTUNITY_STATUSES:
        raise ToolError(f"status must be one of {', '.join(OPPORTUNITY_STATUSES)}")
    body = {}
    if stage is not None:
        current = _get(f"/opportunities/{opportunity_id}")["opportunity"]
        pipelines = _get("/opportunities/pipelines", {"locationId": _location_id()}).get("pipelines", [])
        pipeline = next(p for p in pipelines if p["id"] == current["pipelineId"])
        matches = [s["id"] for s in pipeline["stages"] if s["name"].lower() == stage.lower()]
        if not matches:
            names = ", ".join(s["name"] for s in pipeline["stages"])
            raise ToolError(f"No stage named {stage!r} in {pipeline['name']}; stages: {names}")
        body["pipelineStageId"] = matches[0]
    if status is not None:
        body["status"] = status
    response = _put(f"/opportunities/{opportunity_id}", body)
    updated = response.get("opportunity", response)
    retval = _opportunity_view(updated, _stage_names())
    return retval


if WRITES_ENABLED:
    mcp.tool(annotations=WRITE)(crm_update_opportunity_status)


def main() -> None:
    for name in ("CRM_CTOX_TOKEN", "CRM_CTOX_LOCATION_ID"):
        if not os.environ.get(name):
            raise SystemExit(f"{name} is not set")
    mcp.run(transport="streamable-http", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
