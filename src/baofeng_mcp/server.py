"""baofeng_mcp.server — MCP server exposing Baofeng radio control tools.

This is the Model Context Protocol server that lets any MCP-compatible AI
agent (Claude, GLM, etc.) control a Baofeng DMR radio through natural language.

Run with: python -m baofeng_mcp.server  (or: baofeng-mcp after install)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .radio import BaofengRadio, Channel, DEFAULT_PORT, DEFAULT_BAUD

# ── Initialize ─────────────────────────────────────────────────────
mcp = FastMCP(
    "baofeng",
    instructions=(
        "Control a Baofeng DM-32UV DMR radio. You can detect the radio, "
        "read/write codeplugs, manage channels, and (eventually) send DMR "
        "text messages. Always call detect_radio first to verify the radio "
        "is connected before other operations."
    ),
)

# Global radio instance (lazy-connected)
_radio: BaofengRadio | None = None


def _get_radio() -> BaofengRadio:
    global _radio
    if _radio is None:
        port = os.environ.get("BAOFENG_PORT", DEFAULT_PORT)
        baud = int(os.environ.get("BAOFENG_BAUD", str(DEFAULT_BAUD)))
        _radio = BaofengRadio(port=port, baud=baud)
    return _radio


# ── Tools ──────────────────────────────────────────────────────────


@mcp.tool()
def detect_radio() -> str:
    """Detect if a Baofeng radio is connected and responding.

    Returns JSON with: port, baud, model, responding (bool), handshake bytes.
    Call this FIRST before any other radio operation.
    """
    radio = _get_radio()
    info = radio.detect()
    radio.disconnect()
    return json.dumps(
        {
            "port": info.port,
            "baud": info.baud,
            "model": info.model,
            "responding": info.responding,
            "handshake_hex": info.raw_handshake.hex() if info.raw_handshake else "",
            "message": (
                f"Baofeng {info.model} detected on {info.port} — responding."
                if info.responding
                else f"No radio responding on {info.port}. Check: cable connected? "
                f"Radio powered ON?"
            ),
        },
        indent=2,
    )


@mcp.tool()
def get_radio_info() -> str:
    """Get radio model, firmware version, and DMR ID (if available).

    Returns JSON with radio details.
    """
    radio = _get_radio()
    info = radio.detect()
    radio.disconnect()
    return json.dumps(
        {
            "model": info.model,
            "port": info.port,
            "baud": info.baud,
            "responding": info.responding,
            "note": "Firmware version and DMR ID require codeplug read (in progress)",
        },
        indent=2,
    )


@mcp.tool()
def read_codeplug() -> str:
    """Read the current codeplug (channel list + settings) from the radio.

    Returns JSON with all channels, zones, and DMR settings.
    WARNING: This reads from the radio — it takes ~30 seconds.
    """
    radio = _get_radio()
    result = radio.read_codeplug()
    radio.disconnect()
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def backup_radio(filename: str = "") -> str:
    """Read the current codeplug and save it as a backup file.

    ALWAYS do this before writing a new codeplug, so you can restore if needed.
    Args:
        filename: Where to save the backup. Default: backups/radio_backup_<date>.data
    """
    if not filename:
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        filename = str(backup_dir / f"radio_backup_{ts}.data")
    radio = _get_radio()
    result = radio.read_codeplug()
    radio.disconnect()
    # TODO: save the raw binary codeplug once read_codeplug is implemented
    return json.dumps(
        {
            "status": "planned",
            "backup_path": filename,
            "detail": (
                "Backup will be saved here once the Flash Read protocol "
                "is fully implemented. For now, use the CPS GUI: "
                "Program → Read Radio → File → Save As"
            ),
        },
        indent=2,
    )


@mcp.tool()
def list_channels() -> str:
    """List all channels currently programmed on the radio.

    Returns JSON with a list of channels (name, frequency, mode, etc.).
    """
    radio = _get_radio()
    cp = radio.read_codeplug()
    radio.disconnect()
    channels = cp.get("channels", [])
    return json.dumps(
        {
            "count": len(channels),
            "channels": channels,
            "note": cp.get("status", ""),
        },
        indent=2,
        default=str,
    )


@mcp.tool()
def add_channel(
    name: str,
    freq_rx_mhz: float,
    freq_tx_mhz: float = 0,
    mode: str = "FM",
    bandwidth_khz: float = 12.5,
    power: str = "HIGH",
    rx_only: bool = False,
    zone: str = "",
    color_code: int = 1,
    time_slot: int = 1,
    talk_group: int = 1,
) -> str:
    """Add a single channel to the radio's codeplug.

    Args:
        name: Channel name (max ~16 chars on the DM-32UV display)
        freq_rx_mhz: Receive frequency in MHz (e.g. 476.425 for UHF CB ch1)
        freq_tx_mhz: Transmit frequency (default = same as RX; set different for repeaters)
        mode: Modulation — "FM" (analog) or "DMR" (digital)
        bandwidth_khz: Channel bandwidth (12.5 for narrow, 25 for wide)
        power: "HIGH" or "LOW"
        rx_only: True = receive only (no transmit — for monitoring)
        zone: Zone name to assign this channel to
        color_code: DMR color code (1-15, for DMR mode only)
        time_slot: DMR time slot (1 or 2, for DMR mode only)
        talk_group: DMR talk group ID (for DMR mode only)

    Returns confirmation JSON.
    """
    ch = Channel(
        name=name,
        freq_rx=freq_rx_mhz,
        freq_tx=freq_tx_mhz or freq_rx_mhz,
        mode=mode,
        bandwidth=bandwidth_khz,
        power=power,
        rx_only=rx_only,
        zone=zone,
        color_code=color_code,
        time_slot=time_slot,
        talk_group=talk_group,
    )
    # TODO: actually write to radio once write_codeplug is implemented
    return json.dumps(
        {
            "status": "queued",
            "channel": ch.to_dict(),
            "detail": (
                "Channel prepared. Will be written when write_codeplug "
                "is called. Full serial write protocol in progress."
            ),
        },
        indent=2,
    )


@mcp.tool()
def add_channels_batch(channels_json: str) -> str:
    """Add multiple channels at once from a JSON string.

    Args:
        channels_json: JSON array of channel objects. Each has:
            name, freq_rx_mhz, freq_tx_mhz (optional), mode (optional),
            bandwidth_khz (optional), power (optional), rx_only (optional),
            zone (optional), color_code/time_slot/talk_group (DMR only)

    Example:
        [{"name":"CB01","freq_rx_mhz":476.425,"zone":"UHF-CB"},
         {"name":"CB02","freq_rx_mhz":476.4375,"zone":"UHF-CB"}]

    Returns confirmation with count.
    """
    try:
        channels = json.loads(channels_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"}, indent=2)
    if not isinstance(channels, list):
        return json.dumps({"error": "Expected a JSON array of channels"}, indent=2)
    prepared = []
    for ch_data in channels:
        ch = Channel(
            name=ch_data.get("name", ""),
            freq_rx=ch_data.get("freq_rx_mhz", 0),
            freq_tx=ch_data.get("freq_tx_mhz", 0) or ch_data.get("freq_rx_mhz", 0),
            mode=ch_data.get("mode", "FM"),
            bandwidth=ch_data.get("bandwidth_khz", 12.5),
            power=ch_data.get("power", "HIGH"),
            rx_only=ch_data.get("rx_only", False),
            zone=ch_data.get("zone", ""),
        )
        prepared.append(ch.to_dict())
    return json.dumps(
        {
            "status": "queued",
            "count": len(prepared),
            "channels": prepared,
            "detail": f"{len(prepared)} channels prepared for write.",
        },
        indent=2,
    )


@mcp.tool()
def load_cb_channels(band: str = "uhf") -> str:
    """Load all Australian CB channels (a convenience batch operation).

    Args:
        band: "uhf" for UHF CB (80 channels, 476-477 MHz) or "both" for all.

    Returns confirmation with the channel list that would be loaded.
    """
    channels = []
    if band in ("uhf", "both"):
        for ch_num in range(1, 81):
            freq = 476.4250 + (ch_num - 1) * 0.0125
            channels.append(
                {
                    "name": f"CB{ch_num:02d}",
                    "freq_rx_mhz": round(freq, 4),
                    "freq_tx_mhz": round(freq, 4),
                    "mode": "FM",
                    "bandwidth_khz": 12.5,
                    "power": "HIGH",
                    "zone": "UHF-CB",
                }
            )
    return add_channels_batch(json.dumps(channels))


@mcp.tool()
def send_dmr_text(callsign: str, message: str) -> str:
    """Send a DMR text message to another radio.

    Args:
        callsign: Recipient callsign or DMR ID
        message: Text message (max 280 characters for DMR)

    Returns confirmation.
    """
    if len(message) > 280:
        return json.dumps(
            {
                "error": "Message too long (DMR max is 280 characters)",
                "length": len(message),
            },
            indent=2,
        )
    radio = _get_radio()
    result = radio.send_dmr_text(callsign, message)
    radio.disconnect()
    return json.dumps(result, indent=2)


@mcp.tool()
def read_dmr_messages() -> str:
    """Read received DMR text messages from the radio inbox.

    Returns JSON with a list of received messages.
    """
    radio = _get_radio()
    messages = radio.read_dmr_messages()
    radio.disconnect()
    return json.dumps(
        {
            "count": len(messages),
            "messages": messages,
        },
        indent=2,
        default=str,
    )


@mcp.tool()
def get_battery() -> str:
    """Get the radio's battery level and charging status.

    Returns JSON with battery percentage and charging state.
    """
    radio = _get_radio()
    result = radio.get_battery()
    radio.disconnect()
    return json.dumps(result, indent=2)


# ── Resources (read-only data) ─────────────────────────────────────


@mcp.resource("baofeng://radio/status")
def radio_status() -> str:
    """Current radio connection status."""
    radio = _get_radio()
    info = radio.detect()
    radio.disconnect()
    return json.dumps(
        {
            "connected": info.responding,
            "port": info.port,
            "model": info.model,
        },
        indent=2,
    )


@mcp.resource("baofeng://channels/au-uhf-cb")
def au_uhf_cb_reference() -> str:
    """Australian UHF CB channel frequency reference (80 channels)."""
    channels = []
    for ch in range(1, 81):
        freq = 476.4250 + (ch - 1) * 0.0125
        channels.append({"channel": ch, "frequency_mhz": round(freq, 4)})
    return json.dumps({"band": "AU UHF CB", "channels": channels}, indent=2)


# ── Entry point ────────────────────────────────────────────────────


def main():
    """Run the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
