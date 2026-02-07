"""MCP stdio server exposing soccer analytics tools to Claude Code."""

import base64
import json
import logging
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

# Log to stderr to avoid corrupting MCP stdio transport
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

API_URL = os.environ.get("SOCCER_ANALYTICS_API_URL", "http://localhost:8004")

mcp = FastMCP("soccer-analytics")


async def _api_get(path: str) -> httpx.Response:
    """Make a GET request to the Soccer Analytics API."""
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as client:
        return await client.get(path)


@mcp.tool()
async def parse_session_plan(plan_id: str | None = None) -> str:
    """Query stored soccer session plans.

    Args:
        plan_id: Optional UUID of a specific session plan. If omitted, lists all stored plans.
    """
    if plan_id:
        resp = await _api_get(f"/api/sessions/{plan_id}")
        if resp.status_code == 404:
            return json.dumps({"error": f"Session plan {plan_id} not found"})
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)
    else:
        resp = await _api_get("/api/sessions")
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
async def analyze_tactical_drill(
    plan_id: str,
    drill_index: int,
    render_diagram: bool = False,
) -> str:
    """Analyze a specific drill from a session plan with tactical context.

    Args:
        plan_id: UUID of the session plan.
        drill_index: Zero-based index of the drill within the session plan.
        render_diagram: If true, include a diagram URL in the response.
    """
    resp = await _api_get(f"/api/sessions/{plan_id}/drills/{drill_index}")
    if resp.status_code == 404:
        return json.dumps({"error": resp.json().get("detail", "Not found")})
    resp.raise_for_status()

    result = resp.json()
    if render_diagram:
        result["diagram_url"] = (
            f"{API_URL}/api/sessions/{plan_id}/drills/{drill_index}/diagram"
        )

    return json.dumps(result, indent=2)


@mcp.tool()
async def render_drill_diagram(
    plan_id: str,
    drill_index: int,
    format: str = "png",
) -> str:
    """Render a pitch diagram for a drill and return it as a base64-encoded image.

    Args:
        plan_id: UUID of the session plan.
        drill_index: Zero-based index of the drill within the session plan.
        format: Image format — 'png' or 'pdf'.
    """
    if format not in ("png", "pdf"):
        return json.dumps({"error": "Format must be 'png' or 'pdf'"})

    resp = await _api_get(
        f"/api/sessions/{plan_id}/drills/{drill_index}/diagram?fmt={format}"
    )
    if resp.status_code == 404:
        return json.dumps({"error": resp.json().get("detail", "Not found")})
    resp.raise_for_status()

    encoded = base64.b64encode(resp.content).decode("ascii")
    media_type = "image/png" if format == "png" else "application/pdf"
    return json.dumps({
        "media_type": media_type,
        "data": encoded,
        "size_bytes": len(resp.content),
    })


def main():
    """Run the MCP server on stdio transport."""
    mcp.run(transport="stdio")
