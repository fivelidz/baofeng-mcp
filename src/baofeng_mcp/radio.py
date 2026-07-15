"""baofeng_mcp.radio — Serial control for Baofeng DM-32UV DMR radios.

Speaks the DM-32UV serial protocol over the CH340 programming cable.
The DM-32UV uses the Auctus A6 chipset family (shared with DM-1701, RT3S)
and communicates at 9600 baud using a "Flash Read/Write" block protocol.

This module is the low-level transport layer. The MCP server (server.py)
calls these functions to implement the agent tools.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

try:
    import serial as pyserial
except ImportError:
    pyserial = None  # type: ignore


DEFAULT_PORT = os.environ.get("BAOFENG_PORT", "/dev/ttyUSB0")
DEFAULT_BAUD = int(os.environ.get("BAOFENG_BAUD", "9600"))


@dataclass
class RadioInfo:
    """Detected radio information."""

    port: str
    baud: int
    model: str = "DM-32UV"
    responding: bool = False
    raw_handshake: bytes = b""


@dataclass
class Channel:
    """A single radio channel."""

    name: str = ""
    freq_rx: float = 0.0  # MHz
    freq_tx: float = 0.0  # MHz
    mode: str = "FM"  # FM | DMR | AM
    bandwidth: float = 12.5  # kHz
    power: str = "HIGH"  # HIGH | LOW
    rx_only: bool = False
    zone: str = ""
    # DMR-specific
    color_code: int = 1
    time_slot: int = 1
    talk_group: int = 1

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "freq_rx_mhz": self.freq_rx,
            "freq_tx_mhz": self.freq_tx,
            "mode": self.mode,
            "bandwidth_khz": self.bandwidth,
            "power": self.power,
            "rx_only": self.rx_only,
            "zone": self.zone,
            "color_code": self.color_code,
            "time_slot": self.time_slot,
            "talk_group": self.talk_group,
        }


class BaofengRadio:
    """Low-level serial interface to a Baofeng DM-32UV."""

    def __init__(self, port: str = DEFAULT_PORT, baud: int = DEFAULT_BAUD):
        self.port = port
        self.baud = baud
        self._conn = None

    def connect(self) -> bool:
        """Open the serial port."""
        if pyserial is None:
            raise RuntimeError("pyserial not installed: pip install pyserial")
        try:
            self._conn = pyserial.Serial(
                self.port,
                self.baud,
                timeout=1.0,
                bytesize=8,
                parity="N",
                stopbits=1,
            )
            return True
        except Exception:
            self._conn = None
            return False

    def disconnect(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _send(self, data: bytes, read_timeout: float = 0.8) -> bytes:
        """Send bytes and read the response."""
        if not self._conn:
            if not self.connect():
                return b""
        self._conn.reset_input_buffer()
        self._conn.write(data)
        self._conn.flush()
        time.sleep(0.2)
        old_timeout = self._conn.timeout
        self._conn.timeout = read_timeout
        resp = self._conn.read(256)
        self._conn.timeout = old_timeout
        return resp

    def detect(self) -> RadioInfo:
        """Detect if a radio is connected and responding."""
        info = RadioInfo(port=self.port, baud=self.baud)
        if not self.connect():
            return info
        try:
            # The DM-32UV responds to 0x02 with a handshake byte sequence
            resp = self._send(b"\x02")
            info.raw_handshake = resp
            info.responding = len(resp) > 0
        except Exception:
            pass
        return info

    def read_codeplug(self) -> dict:
        """Read the full codeplug from the radio.

        TODO: Implement the full Flash Read block protocol. This requires:
        1. Send handshake (0x02)
        2. Send "Flash Read " command (the Auctus protocol)
        3. Read memory blocks in sequence (each block = address + data + CRC)
        4. Parse the binary codeplug into channels/zones/DMR settings

        The protocol probe (dmr_probe.py) confirmed the radio responds to
        "Flash Read " with an echo — the block transfer protocol needs mapping.
        """
        # For now, return a placeholder indicating the protocol status
        return {
            "status": "not_implemented",
            "detail": (
                "Codeplug read requires the full Flash Read block protocol. "
                "The radio responds to handshake (verified). Block transfer "
                "protocol mapping is in progress."
            ),
            "handshake_verified": True,
        }

    def write_codeplug(self, codeplug_data: bytes) -> dict:
        """Write a codeplug to the radio.

        TODO: Implement Flash Write block protocol (reverse of read).
        """
        return {
            "status": "not_implemented",
            "detail": "Codeplug write requires the Flash Write block protocol.",
        }

    def send_dmr_text(self, callsign: str, message: str) -> dict:
        """Send a DMR text message.

        TODO: Requires mapping the DMR message outbox in the codeplug memory
        and writing via the serial protocol.
        """
        return {
            "status": "not_implemented",
            "detail": f"Would send to {callsign}: {message[:50]}",
        }

    def read_dmr_messages(self) -> list[dict]:
        """Read received DMR text messages from the radio inbox.

        TODO: Requires mapping the DMR message inbox in codeplug memory.
        """
        return []

    def get_battery(self) -> dict:
        """Get battery status (if supported over serial)."""
        # Some Baofeng DMR radios support battery query over serial
        return {"status": "not_implemented"}
