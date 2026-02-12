# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Home Assistant Smart Home Configuration Repository** running Home Assistant 2026.1.1. It's a YAML-based declarative configuration system - not a traditional build-based project.

## Common Commands

### Index Home Context
```bash
/index-home                      # Run the slash command
python3 .claude/build-index.py   # Or run directly
```
Fetches complete home context from Home Assistant API and saves to `.claude/home-index.json`. Includes:
- **707 entities** across **11 areas** with states and area assignments
- **122 devices** with manufacturer, model, and health status
- **Relationship mapping**: automation→entity, device→entity, area→device
- **Change tracking**: compares to previous index, shows what went offline/online

### Running Home Assistant
Home Assistant runs as a containerized service. Access:
- UI: https://home.wjk.nz (external) or `http://192.168.0.203:8123` (local)
- API: `https://home.wjk.nz/api/` with Bearer token from `.claude/ha-token`
- Credentials: Ask user if not provided

### Traffic Camera Scripts
```bash
# Download mode - scrapes camera images
./scripts/download_traffic_cam.sh --mode download

# Animate mode - generates WebP animations
./scripts/download_traffic_cam.sh --mode animate --period 15min|1hr|4hr
```

### Testing
No traditional test suite. Validation is done through:
- Home Assistant UI configuration validation
- Automation simulation/dry-run in the HA UI
- Service calls via curl to test API endpoints

## Architecture

### Directory Structure
- `configuration.yaml` - Core Home Assistant config (http, zha, api, templates)
- `automations.yaml` - Motion-sensor and energy automations
- `scenes.yaml` - Predefined scene states
- `scripts.yaml` - Custom service definitions
- `blueprints/` - Reusable automation/script templates (uses Blackshome Sensor Light v8.2)
- `esphome/` - ESP32/ESP8266 device firmware configs (kitchen LEDs, outdoor relay controller)
- `zhaquirks/` - Custom Zigbee device quirks (Tuya garage door opener)
- `scripts/` - Bash utilities for media processing
- `www/community/` - Lovelace UI community cards (mushroom, calendar-card-pro, etc.)
- `.claude/` - Claude Code tools and context:
  - `commands/index-home.md` - `/index-home` slash command
  - `build-index.py` - Script to fetch HA data via API
  - `ha-token` - Long-lived API token (gitignored)
  - `home-index.json` - Current home context index (gitignored)
  - `home-index.previous.json` - Previous index for change tracking (gitignored)

### Key Integrations
- **Zigbee (ZHA)**: Primary protocol for smart devices (motion sensors, lights, contact sensors)
- **ESPHome**: Microcontroller management with PWM LED drivers and relay controllers
- **Flick Energy**: Dynamic electricity pricing with template sensors
- **Whisper TTS**: Local text-to-speech service on port 5000

### Configuration Patterns
- **Blueprints**: Reusable automation templates (avoid code duplication)
- **Template sensors**: Jinja2 templating for derived states (e.g., `sensor.flick_pricing_period`)
- **Modular YAML**: Uses `!include` directives for separation
- **Secrets management**: `secrets.yaml` excluded from version control

### Custom Device Support
- `zhaquirks/ts0601_garage.py`: Python quirk for Tuya garage door opener - maps data points to Home Assistant entities and handles vendor-specific protocol

## Git & GitHub

- **Remote is HTTPS**: `https://github.com/wjkay/TheHome.git` — DO NOT change to SSH
- **Auth**: `gh` CLI is the credential helper. If `git push` fails, just run `gh auth login` — do not change the remote URL, do not switch protocols, do not modify `~/.config/gh/hosts.yml`
- **Never change git remote URLs** without explicit user instruction

## Important Notes

- **No build step**: YAML configuration is interpreted at runtime by Home Assistant
- **ESPHome configs contain encrypted API keys**: Review carefully before modifying
- **Shell scripts use ImageMagick** (`magick`) for WebP animation generation
- `.storage/` contains runtime state and is excluded from git
