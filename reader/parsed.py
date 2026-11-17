"""Decode project FNP1 packets; no USB access or claim of calibration accuracy."""
from dataclasses import dataclass
import json
import math
import struct
import time
import zlib

# Independently extracted stock V1.0.7 renderer map; see research-protocol/
# stock-display-map.json. These are labels, not hardware range guarantees.
UNITS = ('mV', 'V', 'Ω', 'kΩ', 'MΩ', 'nF', 'uF', 'mF', 'F', '℃', 'uA', 'mA', 'A', '℉')
SPECIAL = ('', 'AUTO', '.OL', ' ', 'CAL', 'PAS', 'Er1', 'Er2', 'Er3', 'ErC')


class PacketError(ValueError):
    """Malformed or unsupported telemetry; no numeric reading may be emitted."""


@dataclass(frozen=True)
class Sample:
    kind: str
    sequence: int | None = None
    value: float | None = None
    text: str | None = None
    unit: str | None = None
    decimals: int | None = None
    special: int | None = None
    relative: bool = False
    generation: int | None = None


def parse_packet(packet: bytes) -> Sample:
    if len(packet) != 64:
        raise PacketError('expected exactly 64 bytes')
    if packet[:4] != b'FNP1' or packet[4:6] != b'\x01\x40':
        raise PacketError('unsupported magic, version or packet size')
    if zlib.crc32(packet[:60]) != struct.unpack_from('<I', packet, 60)[0]:
        raise PacketError('CRC mismatch')
    flags, mode = packet[6:8]
    if flags & ~0x0f:
        raise PacketError('unknown flag bits')
    if any(packet[33:60]):
        raise PacketError('reserved bytes are nonzero')
    if flags in (0, 2):
        if any(packet[7:60]):
            raise PacketError('noncanonical empty or BUSY packet')
        return Sample('busy' if flags == 2 else 'no_data')
    if flags & 2 or not flags & 4:
        raise PacketError('inconsistent BUSY/sample-present flags')
    if mode != 1 or not flags & 8:
        raise PacketError('sample is not from active multimeter mode')
    sequence, generation = struct.unpack_from('<II', packet, 8)
    value = struct.unpack_from('<f', packet, 20)[0]
    decimals, special, unit_index = packet[24], packet[25], packet[28]
    if not math.isfinite(value):
        raise PacketError('nonfinite stock float')
    if decimals > 4:
        raise PacketError('unknown stock decimal precision')
    if special >= len(SPECIAL):
        raise PacketError('unknown stock result status')
    if unit_index >= len(UNITS) and unit_index != 0xff:
        raise PacketError('unknown stock unit index')
    # Relative mode in stock is enabled by any nonzero byte, not just 1.
    relative = packet[32] != 0
    if generation & 1:
        # Defensive: firmware normally emits canonical no-data during a UI
        # transition. Never establish a baseline from an odd generation.
        return Sample('transition', generation=generation)
    if special:
        return Sample('status', sequence, text=SPECIAL[special], special=special,
                      relative=relative, generation=generation)
    if not flags & 1:
        return Sample('no_numeric_commit', sequence, relative=relative, generation=generation)
    if unit_index == 0xff:
        raise PacketError('numeric sample has no unit')
    return Sample('numeric', sequence, value, f'{value:.{decimals}f}',
                  UNITS[unit_index], decimals, 0, relative, generation)


class Freshness:
    """Host receipt-time freshness; monotonic counters with uint32 wrap.

    First coherent sample establishes a baseline but emits no measurement or
    status until the counter advances within the same generation. Every change
    of generation starts a new baseline, including rollover/restart. A duplicate
    packet never refreshes its age. A different packet at the same
    sequence, or a backwards/ambiguous counter jump, is rejected. A transport
    disconnect must call disconnect(); reconnection starts a new counter epoch.
    """
    def __init__(self, max_age=1.0, clock=time.monotonic):
        if not math.isfinite(max_age) or max_age <= 0:
            raise ValueError('max_age must be finite and positive')
        self.max_age = max_age
        self.clock = clock
        self.disconnect()

    def disconnect(self):
        self._sequence = None
        self._generation = None
        self._awaiting_advance = True
        self._last_packet = None
        self._advanced_at = None
        self._sample = Sample('disconnected')
        self._last_now = None

    def _now(self, now):
        now = self.clock() if now is None else now
        if not math.isfinite(now) or (self._last_now is not None and now < self._last_now):
            self._sample = Sample('invalid')
            raise ValueError('host clock must be finite and monotonic')
        self._last_now = now
        return now

    def accept(self, packet, now=None):
        now = self._now(now)
        try:
            sample = parse_packet(packet)
            if sample.kind == 'transition':
                self._sequence = None
                self._generation = None
                self._last_packet = None
                self._advanced_at = None
                self._awaiting_advance = True
            if sample.sequence is not None:
                if self._generation != sample.generation:
                    self._sequence = None
                    self._last_packet = None
                    self._advanced_at = None
                    self._awaiting_advance = True
                if self._sequence is not None:
                    delta = (sample.sequence - self._sequence) & 0xffffffff
                    if delta == 0:
                        if bytes(packet) != self._last_packet:
                            raise PacketError('same counter carries different payload')
                    elif delta >= 0x80000000:
                        raise PacketError('backwards or ambiguous sample counter; reconnect explicitly')
                    else:
                        self._advanced_at = now
                        self._awaiting_advance = False
                else:
                    self._advanced_at = now
                self._sequence = sample.sequence
                self._generation = sample.generation
                self._last_packet = bytes(packet)
            self._sample = sample
        except PacketError:
            self.disconnect()
            self._last_now = now
            self._sample = Sample('invalid')
            raise
        return self.view(now)

    def view(self, now=None):
        now = self._now(now)
        sample = self._sample
        age = None if self._advanced_at is None else now - self._advanced_at
        stale = sample.sequence is not None and age is not None and age >= self.max_age
        awaiting = sample.sequence is not None and self._awaiting_advance
        state = 'stale' if stale else 'awaiting_new_sample' if awaiting else sample.kind
        out = {'state': state,
               'sequence': sample.sequence, 'generation': sample.generation,
               'age_seconds': age,
               'value': None, 'display': None, 'unit': None,
               'relative': sample.relative}
        if not stale and not awaiting and sample.kind == 'numeric':
            out.update(value=sample.value, display=sample.text, unit=sample.unit)
        elif not stale and not awaiting and sample.kind == 'status':
            out.update(display=sample.text, special_result=sample.special)
        return out


def decode_stream(source, destination, tracker=None):
    """Read binary file/stdin stream, write JSONL to text stream; no device I/O.

    The caller owns and closes streams. Truncated records fail; earlier complete
    JSON records remain written. Recorded files have playback receipt times,
    not historical acquisition times. Live USB will need an identity handshake.
    """
    tracker = Freshness() if tracker is None else tracker
    while True:
        packet = source.read(64)
        if not packet:
            return
        # A stream is allowed to return fewer bytes before EOF.
        while len(packet) < 64:
            more = source.read(64 - len(packet))
            if not more:
                raise PacketError('truncated final packet')
            packet += more
        result = tracker.accept(packet)
        destination.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
