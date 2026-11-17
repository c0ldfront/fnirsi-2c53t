"""Fake-device tests: never import PyUSB or enumerate real USB hardware."""
import unittest
from parsed import Freshness, PacketError
from test_parsed import packet, seal
from transport import Reader, parse_identity, FIRMWARE_SHA256


def identity():
    p = bytearray(64); p[:8] = b'FNI1\x01\x40\x01\x00'
    p[8:40] = bytes.fromhex(FIRMWARE_SHA256)
    return seal(p)


class FakeDevice:
    def __init__(self, replies):
        self.replies = list(replies); self.calls = []
    def ctrl_transfer(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception): raise reply
        return reply


class TransportTests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(parse_identity(identity())['firmware_sha256'], FIRMWARE_SHA256)
        for offset in (*range(8), 8, 39, *range(40,60)):
            p = bytearray(identity()); p[offset] ^= 1
            with self.assertRaises(PacketError): parse_identity(seal(p))
        for p in (identity()[:-1], identity()+b'x', identity()[:63]+b'x'):
            with self.assertRaises(PacketError): parse_identity(p)

    def test_handshake_is_required_and_requests_are_fixed_IN(self):
        dev = FakeDevice([identity(), packet()]); reader = Reader(dev)
        with self.assertRaises(PacketError): reader.read(now=0)
        self.assertEqual(dev.calls, [])
        reader.handshake(); self.assertEqual(reader.read(now=0)['state'], 'awaiting_new_sample')
        for (args, kwargs), request in zip(dev.calls,(0x50,0x51)):
            self.assertEqual(args,(0xc0,request))
            self.assertEqual(kwargs,dict(wValue=0x3154,wIndex=0,data_or_wLength=64,timeout=1000))

    def test_bad_identity_never_reads_data(self):
        dev = FakeDevice([bytes(64)]); reader = Reader(dev)
        with self.assertRaises(PacketError): reader.handshake()
        with self.assertRaises(PacketError): reader.read(now=0)
        self.assertEqual(len(dev.calls),1)

    def test_transfer_error_clears_number_and_demands_new_handshake(self):
        dev = FakeDevice([identity(),packet(seq=100),TimeoutError('synthetic timeout'),identity(),packet(seq=0)])
        reader = Reader(dev, freshness=Freshness(clock=lambda:0))
        reader.handshake(); reader.read()
        with self.assertRaises(TimeoutError): reader.read()
        self.assertIsNone(reader.freshness.view()['value'])
        self.assertFalse(reader.ready)
        with self.assertRaises(PacketError): reader.read()
        reader.handshake()
        first = reader.read()
        self.assertEqual(first['sequence'],0)
        self.assertEqual(first['state'],'awaiting_new_sample')
        self.assertIsNone(first['value'])

    def test_close_is_idempotent_and_prevents_queries(self):
        dev = FakeDevice([identity()]); reader = Reader(dev)
        reader.handshake(); released = []
        reader._release = lambda: released.append(True)
        reader.close(); reader.close()
        self.assertEqual(released, [True])
        with self.assertRaises(PacketError): reader.handshake()
        self.assertEqual(len(dev.calls), 1)

    def test_bad_data_invalidates_session(self):
        reader = Reader(FakeDevice([identity(),bytes(64)]))
        reader.handshake()
        with self.assertRaises(PacketError): reader.read(now=0)
        self.assertFalse(reader.ready)


if __name__ == '__main__': unittest.main(verbosity=2)
