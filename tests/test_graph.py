"""The hub is only a hub if the graph is fully connected and never overclaims.

These are the invariants the whole wiring rests on. If one fails, the board is
telling the owner something untrue about his own backlog.
"""
from fastapi.testclient import TestClient

from app import catalog, graph
from app.config import get_settings
from app.ideas import registry as ideas
from app.ideas import wiring
from app.main import app
from app.registry import SYSTEMS

client = TestClient(app)
settings = get_settings()


# --- the populate is complete ---------------------------------------------

def test_every_idea_lands_on_a_real_system():
    keys = {s.key for s in SYSTEMS}
    for i in ideas.all_ideas():
        assert i.systems, f"{i.id} is not placed on any system"
        assert i.primary_system in i.systems
        bad = [s for s in i.systems if s not in keys]
        assert not bad, f"{i.id} points at systems that are not on the map: {bad}"


def test_every_idea_endpoint_is_a_real_route():
    paths = catalog.paths()
    for i in ideas.all_ideas():
        bad = [e for e in i.data_endpoints if e not in paths]
        assert not bad, f"{i.id} claims data at routes that do not exist: {bad}"


def test_wiring_covers_the_whole_backlog():
    """Every row in BACKLOG.md is wired explicitly, not left to a default."""
    unwired = [i.id for i in ideas.all_ideas() if i.id not in wiring.WIRING]
    assert not unwired, f"backlog rows with no wiring: {unwired}"


def test_a_new_backlog_row_still_lands_somewhere():
    """Adding a row must keep working with no code change — it inherits its
    domain rather than falling off the map."""
    w = wiring.wire_for("S999", "S")
    assert w.systems and w.section
    assert wiring.wire_for("ZZ1", "ZZ").systems  # even an unknown domain


def test_wiring_references_nothing_that_does_not_exist():
    assert wiring.unknown_systems() == set()
    assert wiring.unknown_endpoints() == set()


def test_every_idea_says_what_it_needs():
    silent = [i.id for i in ideas.all_ideas() if i.readiness != "done" and not i.needs]
    assert not silent, f"ideas with no explanation of what is missing: {silent}"


# --- the honesty rules ------------------------------------------------------

def test_a_planned_idea_never_links_as_if_built():
    for i in ideas.all_ideas():
        if i.status == "planned":
            assert i.link == f"/tools/ideas#{i.id}"
            assert i.deliverable is None


def test_no_idea_claims_a_built_page_as_its_data_source():
    """`data_endpoints` are raw data. A page is a finished report, so pointing a
    planned requirement at one would claim work nobody has done."""
    pages = {e.path for e in catalog.ENDPOINTS if e.kind == "page"}
    for i in ideas.all_ideas():
        claimed = [e for e in i.data_endpoints if e in pages]
        assert not claimed, f"{i.id} points at built page(s) {claimed}"


def test_a_blocked_idea_leads_somewhere():
    """"Nothing connected yet" is a dead end unless it says what would fix it."""
    for i in ideas.all_ideas():
        if not i.data_endpoints and i.missing_connectors:
            assert i.unblock, f"{i.id} has neither data nor a way to understand why"


# --- the graph agrees with itself ------------------------------------------

def test_every_node_edge_resolves():
    g = graph.build(settings)
    system_keys = {s["key"] for s in g["systems"]}
    connector_keys = {c["key"] for c in g["connectors"]}
    paths = {e["path"] for e in g["endpoints"]}
    idea_ids = {i["id"] for i in g["ideas"]}

    for s in g["systems"]:
        assert set(s["connectors"]) <= connector_keys
        assert set(s["endpoints"]) <= paths
        assert set(s["idea_ids"]) <= idea_ids
    for c in g["connectors"]:
        assert not c["system"] or c["system"] in system_keys
        assert set(c["endpoints"]) <= paths
        assert set(c["idea_ids"]) <= idea_ids
    for e in g["endpoints"]:
        assert set(e["feeds_ideas"]) <= idea_ids


def test_the_counts_are_the_same_everywhere():
    """/systems, /connectors and the map all slice one join, so they cannot
    report different numbers for the same thing."""
    g = graph.build(settings)
    by_map = {s["key"]: s["ideas"]["total"] for s in g["systems"]}
    from_systems = {s["key"]: s["ideas"]["total"]
                    for s in client.get("/systems").json()["systems"]}
    assert by_map == from_systems


def test_every_live_connector_is_reachable_from_an_endpoint():
    for c in catalog.CONNECTORS:
        if c.live:
            assert catalog.endpoints_of(c.key), f"live connector {c.key} serves no route"


# --- the API surface --------------------------------------------------------

def test_map_returns_the_whole_graph():
    body = client.get("/api/v1/map").json()
    assert body["counts"]["ideas"] == len(ideas.all_ideas())
    assert body["counts"]["systems"] == len(SYSTEMS)
    assert "NOT a built report" in body["data_endpoints_mean"]


def test_map_can_be_narrowed_to_one_system():
    body = client.get("/api/v1/map?system=crm").json()
    assert [s["key"] for s in body["systems"]] == ["crm"]
    assert all("crm" in i["systems"] for i in body["ideas"])


def test_system_detail_lists_its_requirements():
    r = client.get("/systems/nama")
    assert r.status_code == 200
    body = r.json()
    assert body["ideas"]["total"] > 50
    assert all("nama" in i["systems"] for i in body["ideas_detail"])
    assert client.get("/systems/not-a-system").status_code == 404


def test_connector_detail_lists_what_waits_on_it():
    body = client.get("/connectors/ai-layer").json()
    assert body["live"] is False
    assert body["waiting_on_it"], "the AI layer blocks ideas; it must name them"
    assert client.get("/connectors/nope").status_code == 404


def test_ideas_can_be_filtered_by_every_edge():
    for query, check in (
        ("system=crm", lambda i: "crm" in i["systems"]),
        ("connector=sql", lambda i: "sql" in i["connectors"]),
        ("endpoint=/api/v1/finance/customers",
         lambda i: "/api/v1/finance/customers" in i["data_endpoints"]),
        ("section=inventory", lambda i: i["workspace_section"] == "inventory"),
        ("has_data=true", lambda i: bool(i["data_endpoints"])),
        ("has_data=false", lambda i: not i["data_endpoints"]),
    ):
        rows = client.get(f"/api/v1/ideas?{query}").json()["ideas"]
        assert rows, f"filter {query} matched nothing"
        assert all(check(i) for i in rows), f"filter {query} returned a non-match"


def test_planned_system_placeholder_explains_itself():
    r = client.get("/api/v1/academy")
    assert r.status_code == 501
    body = r.json()
    assert body["see"] == "/systems/academy"
    assert "ideas_waiting" in body


def test_workspace_sections_carry_their_coordinates():
    sections = client.get("/api/v1/workspace").json()["sections"]
    keys = {s["key"] for s in sections}
    assert "finance" in keys, "the only source of real balances must be on the dashboard"
    for s in sections:
        assert s["api"], f"section {s['key']} has no way out to its raw data"
