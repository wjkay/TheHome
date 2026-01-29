# Index Home Assistant

Index all devices, entities, areas, automations, and relationships from Home Assistant.

## Usage

```bash
python3 .claude/build-index.py
```

## What It Indexes

### 1. Device Registry
- 122 devices with manufacturer, model, area assignment
- Entity-to-device mappings
- Devices with unavailable entities flagged

### 2. Relationship Mapping
- Automation → entity control mappings
- Entity → automation reverse lookups
- Device → entity mappings
- Area → device mappings

### 3. Change Tracking
- Compares against previous index (`.claude/home-index.previous.json`)
- Detects: new/removed entities, new/removed devices
- Tracks: entities that went unavailable or came back online

## Output

Index file: `.claude/home-index.json` (~300KB)

```json
{
  "indexed_at": "ISO timestamp",
  "ha_version": "2026.1.1",
  "summary": {
    "total_entities": 707,
    "total_devices": 122,
    "total_areas": 11,
    "unavailable_count": 65
  },
  "areas": [...],
  "devices": [...],
  "entities": [...],
  "automations": [...],
  "relationships": {
    "automation_controls": {},
    "entity_controlled_by": {},
    "device_entity_map": {},
    "area_device_map": {}
  },
  "issues": {
    "unavailable_entities": [...],
    "devices_with_issues": [...]
  },
  "changes_since_last": {
    "entities": {"added": [], "removed": []},
    "devices": {"added": [], "removed": []},
    "unavailable": {"now_unavailable": [], "now_available": []}
  }
}
```

## First-Time Setup

If `.claude/ha-token` doesn't exist:
1. Ask user for Home Assistant credentials
2. Login to https://home.wjk.nz
3. Go to Profile > Security > Long-lived access tokens
4. Create token named "Claude Code"
5. Save to `.claude/ha-token`

## Quick Queries

```bash
# Devices with issues
python3 -c "import json; [print(n) for n in json.load(open('.claude/home-index.json'))['issues']['devices_with_issues']]"

# Find entity by name
python3 -c "import json; [print(e['entity_id'], e.get('area_name','')) for e in json.load(open('.claude/home-index.json'))['entities'] if 'kitchen' in e['friendly_name'].lower()]"

# List devices in an area
python3 -c "import json; d=json.load(open('.claude/home-index.json')); [print(dev['name']) for dev in d['devices'] if dev.get('area_name')=='Living Room']"
```
