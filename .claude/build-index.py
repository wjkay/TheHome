#!/usr/bin/env python3
"""Build Home Assistant index from API data."""
import json
import subprocess
import os
from datetime import datetime

HA_URL = "https://home.wjk.nz"
INDEX_FILE = ".claude/home-index.json"
PREVIOUS_INDEX_FILE = ".claude/home-index.previous.json"

def api_call(endpoint, method="GET", data=None):
    """Make an API call to Home Assistant."""
    with open(".claude/ha-token") as f:
        token = f.read().strip()

    cmd = ["curl", "-s", "-H", f"Authorization: Bearer {token}"]

    if method == "POST":
        cmd.extend(["-X", "POST", "-H", "Content-Type: application/json"])
        if data:
            cmd.extend(["-d", json.dumps(data)])

    cmd.append(f"{HA_URL}{endpoint}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

def template_call(template):
    """Execute a template and return result."""
    result = api_call("/api/template", "POST", {"template": template})
    return result

def get_device_ids():
    """Get all device IDs from entities."""
    template = """{% set devices = namespace(ids=[]) %}{% for state in states %}{% set did = device_id(state.entity_id) %}{% if did and did not in devices.ids %}{% set devices.ids = devices.ids + [did] %}{% endif %}{% endfor %}{% for did in devices.ids %}{{ did }}
{% endfor %}"""
    result = template_call(template)
    return [d.strip() for d in result.strip().split("\n") if d.strip()]

def get_device_info(device_id):
    """Get device details."""
    template = f"""{{
  "id": "{device_id}",
  "name": "{{{{ device_attr("{device_id}", "name") | default("unknown") }}}}",
  "manufacturer": "{{{{ device_attr("{device_id}", "manufacturer") | default("") }}}}",
  "model": "{{{{ device_attr("{device_id}", "model") | default("") }}}}",
  "area_id": "{{{{ device_attr("{device_id}", "area_id") | default("") }}}}",
  "area_name": "{{{{ area_name(device_attr("{device_id}", "area_id")) | default("") }}}}"
}}"""
    result = template_call(template)
    try:
        return json.loads(result)
    except:
        return {"id": device_id, "name": "unknown", "error": "failed to parse"}

def get_device_entities(device_id):
    """Get entities for a device."""
    result = template_call(f"{{{{ device_entities('{device_id}') | join(',') }}}}")
    if result.strip():
        return result.strip().split(",")
    return []

def get_automation_entities(automation_entity_id):
    """Try to extract entities referenced by an automation."""
    # Get the automation's attributes which may contain entity references
    result = template_call(f"{{{{ state_attr('{automation_entity_id}', 'entity_id') | default([]) | join(',') }}}}")
    entities = []
    if result.strip():
        entities = result.strip().split(",")
    return entities

def load_previous_index():
    """Load the previous index for change tracking."""
    if os.path.exists(PREVIOUS_INDEX_FILE):
        with open(PREVIOUS_INDEX_FILE) as f:
            return json.load(f)
    return None

def compute_changes(current, previous):
    """Compute changes between current and previous index."""
    if not previous:
        return {"first_index": True}

    changes = {
        "previous_indexed_at": previous.get("indexed_at"),
        "entities": {"added": [], "removed": [], "state_changed": []},
        "devices": {"added": [], "removed": []},
        "unavailable": {"now_unavailable": [], "now_available": []}
    }

    # Entity changes
    prev_entities = {e["entity_id"]: e for e in previous.get("entities", [])}
    curr_entities = {e["entity_id"]: e for e in current.get("entities", [])}

    for eid in curr_entities:
        if eid not in prev_entities:
            changes["entities"]["added"].append(eid)
        elif curr_entities[eid]["state"] != prev_entities[eid]["state"]:
            changes["entities"]["state_changed"].append({
                "entity_id": eid,
                "old_state": prev_entities[eid]["state"],
                "new_state": curr_entities[eid]["state"]
            })

    for eid in prev_entities:
        if eid not in curr_entities:
            changes["entities"]["removed"].append(eid)

    # Device changes
    prev_devices = {d["id"]: d for d in previous.get("devices", [])}
    curr_devices = {d["id"]: d for d in current.get("devices", [])}

    for did in curr_devices:
        if did not in prev_devices:
            changes["devices"]["added"].append(curr_devices[did].get("name", did))

    for did in prev_devices:
        if did not in curr_devices:
            changes["devices"]["removed"].append(prev_devices[did].get("name", did))

    # Unavailable tracking
    prev_unavailable = set(previous.get("issues", {}).get("unavailable_entities", []))
    curr_unavailable = set(current.get("issues", {}).get("unavailable_entities", []))

    changes["unavailable"]["now_unavailable"] = list(curr_unavailable - prev_unavailable)
    changes["unavailable"]["now_available"] = list(prev_unavailable - curr_unavailable)

    return changes

def main():
    print("Fetching states...")
    states_json = api_call("/api/states")
    states = json.loads(states_json)

    print("Fetching config...")
    config_json = api_call("/api/config")
    config = json.loads(config_json)

    # Get areas
    print("Fetching areas...")
    areas_raw = template_call("{% for area in areas() %}{{ area_name(area) }}|{{ area }}\n{% endfor %}")
    areas = {}
    for line in areas_raw.strip().split("\n"):
        if "|" in line:
            name, area_id = line.split("|", 1)
            areas[area_id] = {"id": area_id, "name": name, "entities": [], "devices": []}

    # Get area-entity mappings
    for area_id in areas:
        entities_raw = template_call(f"{{{{ area_entities('{area_id}') | join(',') }}}}")
        if entities_raw.strip():
            areas[area_id]["entities"] = entities_raw.strip().split(",")

    # Get devices
    print("Fetching devices...")
    device_ids = get_device_ids()
    devices = []
    entity_to_device = {}

    for i, did in enumerate(device_ids):
        if i % 20 == 0:
            print(f"  Processing device {i+1}/{len(device_ids)}...")

        device = get_device_info(did)
        device["entities"] = get_device_entities(did)

        # Track entity to device mapping
        for eid in device["entities"]:
            entity_to_device[eid] = did

        # Check if device has any unavailable entities
        device["has_unavailable"] = any(
            s["state"] == "unavailable"
            for s in states
            if s["entity_id"] in device["entities"]
        )

        devices.append(device)

        # Add device to area
        if device.get("area_id") and device["area_id"] in areas:
            areas[device["area_id"]]["devices"].append(did)

    # Build entity index
    print("Building entity index...")
    entities = []
    unavailable = []
    for state in states:
        entity = {
            "entity_id": state["entity_id"],
            "state": state["state"],
            "friendly_name": state.get("attributes", {}).get("friendly_name", state["entity_id"]),
            "domain": state["entity_id"].split(".")[0],
        }

        # Add device reference
        if state["entity_id"] in entity_to_device:
            entity["device_id"] = entity_to_device[state["entity_id"]]

        # Find area for this entity
        for area_id, area_data in areas.items():
            if state["entity_id"] in area_data["entities"]:
                entity["area_id"] = area_id
                entity["area_name"] = area_data["name"]
                break

        entities.append(entity)

        if state["state"] == "unavailable":
            unavailable.append(state["entity_id"])

    # Build automations list with relationship mapping
    print("Mapping automation relationships...")
    automations = []
    automation_to_entities = {}

    for state in states:
        if state["entity_id"].startswith("automation."):
            auto = {
                "entity_id": state["entity_id"],
                "alias": state.get("attributes", {}).get("friendly_name", ""),
                "state": state["state"],
                "last_triggered": state.get("attributes", {}).get("last_triggered"),
            }

            # Try to get referenced entities from attributes
            attrs = state.get("attributes", {})
            referenced = []

            # Check common attribute patterns for entity references
            for key in ["entity_id", "target", "service_data"]:
                if key in attrs:
                    val = attrs[key]
                    if isinstance(val, list):
                        referenced.extend([v for v in val if isinstance(v, str) and "." in v])
                    elif isinstance(val, str) and "." in val:
                        referenced.append(val)

            auto["referenced_entities"] = list(set(referenced))
            automations.append(auto)
            automation_to_entities[state["entity_id"]] = auto["referenced_entities"]

    # Build relationship map
    print("Building relationship map...")
    relationships = {
        "automation_controls": automation_to_entities,
        "entity_controlled_by": {},
        "device_entity_map": {d["id"]: d["entities"] for d in devices},
        "area_device_map": {a["id"]: a["devices"] for a in areas.values()},
    }

    # Reverse map: entity -> automations that control it
    for auto_id, entity_list in automation_to_entities.items():
        for eid in entity_list:
            if eid not in relationships["entity_controlled_by"]:
                relationships["entity_controlled_by"][eid] = []
            relationships["entity_controlled_by"][eid].append(auto_id)

    # Count by domain
    domains = {}
    for entity in entities:
        domain = entity["domain"]
        domains[domain] = domains.get(domain, 0) + 1

    # Load previous index for change tracking
    previous = load_previous_index()

    # Build final index
    index = {
        "indexed_at": datetime.now().isoformat(),
        "ha_version": config.get("version", "unknown"),
        "location_name": config.get("location_name", "Home"),
        "summary": {
            "total_entities": len(entities),
            "total_devices": len(devices),
            "total_areas": len(areas),
            "total_automations": len(automations),
            "unavailable_count": len(unavailable),
            "domains": domains,
        },
        "areas": list(areas.values()),
        "devices": devices,
        "entities": entities,
        "automations": automations,
        "relationships": relationships,
        "issues": {
            "unavailable_entities": unavailable,
            "devices_with_issues": [d["name"] for d in devices if d.get("has_unavailable")],
        }
    }

    # Compute changes
    changes = compute_changes(index, previous)
    index["changes_since_last"] = changes

    # Save previous index before overwriting
    if os.path.exists(INDEX_FILE):
        os.rename(INDEX_FILE, PREVIOUS_INDEX_FILE)

    # Write index
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)

    # Print summary
    print("\n" + "="*50)
    print(f"Index created: {len(entities)} entities, {len(devices)} devices, {len(areas)} areas")
    print(f"Automations: {len(automations)}")
    print(f"Unavailable entities: {len(unavailable)}")
    print(f"Devices with issues: {len(index['issues']['devices_with_issues'])}")
    print(f"HA Version: {config.get('version')}")

    # Print changes if not first index
    if not changes.get("first_index"):
        print("\n--- Changes since last index ---")
        if changes["entities"]["added"]:
            print(f"  New entities: {len(changes['entities']['added'])}")
        if changes["entities"]["removed"]:
            print(f"  Removed entities: {len(changes['entities']['removed'])}")
        if changes["devices"]["added"]:
            print(f"  New devices: {changes['devices']['added']}")
        if changes["devices"]["removed"]:
            print(f"  Removed devices: {changes['devices']['removed']}")
        if changes["unavailable"]["now_unavailable"]:
            print(f"  Went unavailable: {changes['unavailable']['now_unavailable']}")
        if changes["unavailable"]["now_available"]:
            print(f"  Came back online: {changes['unavailable']['now_available']}")

if __name__ == "__main__":
    main()
