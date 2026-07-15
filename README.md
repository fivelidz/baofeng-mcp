# baofeng-mcp

**An MCP (Model Context Protocol) server for controlling Baofeng DMR radios.**

Turns any MCP-compatible AI agent (Claude, GLM, etc.) into a radio operator
that can read/write codeplugs, manage channels, send DMR text messages, and
monitor radio status — all through natural language.

## What It Does

```
You: "Load the UHF CB channels onto my radio"
Agent: (calls baofeng_mcp tools) → reads codeplug, adds 80 CB channels, writes to radio

You: "What channels are on the radio right now?"
Agent: (calls read_codeplug) → "You have 16 channels, all factory defaults..."

You: "Send a text message to callsign VK2ABC on channel 3"
Agent: (calls send_dmr_text) → writes message to radio outbox
```

## Supported Radios
- **Baofeng DM-32UV** (primary target — tested)
- **Baofeng DM-1701** (same CPS family)
- **Baofeng DM-1801** (same CPS family)
- Any Baofeng DMR radio using the Auctus A6 chipset + CH340 cable

## MCP Tools Exposed

| Tool | What it does |
|------|-------------|
| `detect_radio` | Detect connected radio, return model + serial port |
| `read_codeplug` | Read the current codeplug from the radio |
| `write_codeplug` | Write a codeplug to the radio |
| `backup_radio` | Read + save the current codeplug as a backup file |
| `list_channels` | List all channels currently on the radio |
| `add_channel` | Add a single channel (name, freq, mode, etc.) |
| `add_channels_batch` | Add multiple channels from a list/CSV |
| `delete_channel` | Delete a channel by index or name |
| `list_zones` | List zone assignments |
| `get_radio_info` | Radio model, firmware, DMR ID, serial number |
| `send_dmr_text` | Send a DMR text message (when protocol is RE'd) |
| `read_dmr_messages` | Read received DMR text messages |
| `get_battery` | Battery level + charging status (if supported) |

## Architecture

```
MCP Client (Claude/GLM/any agent)
        │  (JSON-RPC over stdio)
        ▼
baofeng_mcp server (this project)
        │
        ├── Serial transport (/dev/ttyUSB0 @ 9600)
        │   └── DM-32UV CPS serial protocol
        │
        └── CPS bridge (optional, for complex operations)
            └── Wine + Baofeng CPS v1.60
```

The server speaks the DM-32UV serial protocol directly (no Wine needed for
basic operations). For complex codeplug operations, it can shell out to the
CPS under Wine.

## Quick Start

```bash
# Install
pip install baofeng-mcp

# Run (connects to radio on /dev/ttyUSB0)
baofeng-mcp

# Or with explicit settings
BAOFENG_PORT=/dev/ttyUSB0 BAOFENG_BAUD=9600 baofeng-mcp
```

### Add to Claude Code / MCP client config:
```json
{
  "mcpServers": {
    "baofeng": {
      "command": "baofeng-mcp",
      "env": {
        "BAOFENG_PORT": "/dev/ttyUSB0"
      }
    }
  }
}
```

## Project Structure
```
baofeng_mcp/
├── README.md                   ← This file
├── pyproject.toml              ← Package config (pip installable)
├── src/baofeng_mcp/
│   ├── __init__.py
│   ├── server.py               ← MCP server (exposes tools)
│   ├── radio.py                ← Serial radio control (DM-32UV protocol)
│   ├── codeplug.py             ← Codeplug read/write/parse
│   └── channels.py             ← Channel + zone data models
├── tests/
│   └── test_radio.py
└── examples/
    ├── load_cb_channels.py     ← Example: load AU UHF CB channels
    └── mcp_client_demo.py      ← Example: call tools from Python
```

## Status

- [x] Project scaffold + MCP server framework
- [x] Radio detection + serial handshake (verified working)
- [x] Channel data models + codeplug generator
- [ ] Full codeplug read/write via serial protocol (in progress)
- [ ] DMR text message send/receive (needs protocol RE)
- [ ] PyPI package

## Legal
- Codeplug read/write: legal (you're configuring your own radio)
- TX frequency compliance: user's responsibility (follow your local regulations)
- This project is for **your own radios** — don't clone or program radios you don't own

## License
MIT
