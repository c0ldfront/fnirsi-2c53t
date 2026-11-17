"""Read-only EP0 telemetry client; no discovery or device access at import time."""
import struct
import zlib
from parsed import Freshness, PacketError

FIRMWARE_SHA256 = '83271baa03bcbf15200cfb80fa92a8cd0d7c37889b088d382098dcd2c9e0d2b3'
REQUEST_TYPE = 0xc0
REQUEST_VALUE = 0x3154
IDENTITY_REQUEST = 0x50
PARSED_REQUEST = 0x51


def parse_identity(packet):
    if len(packet) != 64:
        raise PacketError('identity must contain exactly 64 bytes')
    if packet[:8] != b'FNI1\x01\x40\x01\x00':
        raise PacketError('unsupported telemetry identity/protocol')
    if bytes(packet[8:40]).hex() != FIRMWARE_SHA256:
        raise PacketError('telemetry firmware identity mismatch')
    if any(packet[40:60]):
        raise PacketError('identity reserved bytes are nonzero')
    if zlib.crc32(packet[:60]) != struct.unpack_from('<I', packet, 60)[0]:
        raise PacketError('identity CRC mismatch')
    return {'protocol': 1, 'firmware_sha256': FIRMWARE_SHA256}


class Reader:
    """Inject a PyUSB-compatible device; constructor performs no I/O.

    Call handshake() once per connection, then read(). Any transfer/parser error
    invalidates the session and clears freshness; handshake must succeed again.
    Only two fixed device-to-host vendor requests are ever issued.
    """
    def __init__(self, device, timeout_ms=1000, freshness=None):
        if not isinstance(timeout_ms, int) or not 1 <= timeout_ms <= 60000:
            raise ValueError('timeout_ms must be an integer from 1 to 60000')
        self.device = device
        self.timeout_ms = timeout_ms
        self.freshness = Freshness() if freshness is None else freshness
        self.ready = False
        self._release = None
        self._closed = False

    def close(self):
        self.disconnect()
        self._closed = True
        if self._release is not None:
            release, self._release = self._release, None
            release()

    def disconnect(self):
        self.ready = False
        self.freshness.disconnect()

    def _request(self, request):
        # Fixed IN direction, length, index and value. No generic write API.
        return bytes(self.device.ctrl_transfer(REQUEST_TYPE, request,
                     wValue=REQUEST_VALUE, wIndex=0, data_or_wLength=64,
                     timeout=self.timeout_ms))

    def handshake(self):
        if self._closed:
            raise PacketError("reader is closed")
        self.disconnect()
        try:
            identity = parse_identity(self._request(IDENTITY_REQUEST))
            self.ready = True
            return identity
        except Exception:
            self.disconnect()
            raise

    def read(self, now=None):
        if not self.ready:
            raise PacketError('identity handshake required before reading telemetry')
        try:
            return self.freshness.accept(self._request(PARSED_REQUEST), now)
        except Exception:
            self.disconnect()
            raise


def connect_pyusb(vid, pid, serial=None, timeout_ms=1000):
    """Explicit opt-in hardware discovery; NOT called by tests or import.

    VID/PID are caller inputs, never an assertion of identity. Exactly one match
    is required; handshake checks the reported protocol and compiled target hash.
    This is compatibility metadata, not runtime code integrity authentication.
    Does not set configuration, detach drivers, reset USB, or write endpoints.
    PyUSB and a working libusb backend must already be available to the caller.
    """
    if not all(isinstance(v, int) and 0 <= v <= 0xffff for v in (vid, pid)):
        raise ValueError('VID and PID must be unsigned 16-bit integers')
    try:
        import usb.core
        import usb.util
    except ImportError as exc:
        raise RuntimeError('PyUSB is required only for explicit live USB connections') from exc
    selected = None
    try:
        for device in usb.core.find(find_all=True, idVendor=vid, idProduct=pid):
            if serial is not None and device.serial_number != serial:
                usb.util.dispose_resources(device)
                continue
            if selected is not None:
                usb.util.dispose_resources(device)
                raise RuntimeError('multiple matching devices; select a unique serial')
            selected = device
        if selected is None:
            raise RuntimeError('requested USB device not found')
        reader = Reader(selected, timeout_ms)
        reader.handshake()
        reader._release = lambda: usb.util.dispose_resources(selected)
        return reader
    except Exception:
        if selected is not None:
            usb.util.dispose_resources(selected)
        raise
