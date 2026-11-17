"""Synthetic FNP1 decoder tests; never open a USB device."""
import io
import json
import pathlib
import struct
import unittest
import zlib
from parsed import Freshness, PacketError, UNITS, SPECIAL, parse_packet, decode_stream


def seal(p):
    struct.pack_into('<I', p, 60, zlib.crc32(p[:60]))
    return bytes(p)


def packet(seq=1, flags=13, value=1.25, decimals=2, special=0, unit=1, generation=0):
    p = bytearray(64)
    p[:8] = b'FNP1\x01\x40' + bytes([flags, 1])
    struct.pack_into('<II', p, 8, seq, generation)
    struct.pack_into('<f', p, 20, value)
    p[24], p[25], p[28] = decimals, special, unit
    return seal(p)


def empty(flags=0):
    p = bytearray(64)
    p[:7] = b'FNP1\x01\x40' + bytes([flags])
    return seal(p)


class DecoderTests(unittest.TestCase):
    def test_authoritative_map(self):
        authority = json.loads((pathlib.Path(__file__).resolve().parent.parent /
                                'docs/stock-display-map.json').read_text())
        self.assertEqual(list(UNITS), [v['label'] for v in authority['units']])
        self.assertEqual(list(SPECIAL[1:]), [v['label'] for v in authority['special_results']])

    def test_float_is_not_scaled_again(self):
        r = parse_packet(packet(value=-12.375, decimals=3))
        self.assertEqual((r.value, r.text, r.unit), (-12.375, '-12.375', 'V'))

    def test_every_unit_precision_and_result(self):
        for unit in range(14):
            for decimal in range(5):
                r = parse_packet(packet(unit=unit, decimals=decimal))
                self.assertEqual(r.unit, UNITS[unit])
                self.assertEqual(r.text, f'{1.25:.{decimal}f}')
        for status in range(1, 10):
            r = parse_packet(packet(special=status, unit=255))
            self.assertEqual((r.kind, r.text, r.value), ('status', SPECIAL[status], None))

    def test_no_commit_cannot_reuse_old_float(self):
        r = parse_packet(packet(flags=12, value=123.0))
        self.assertEqual((r.kind, r.value, r.unit), ('no_numeric_commit', None, None))

    def test_empty_and_busy_are_canonical(self):
        self.assertEqual(parse_packet(empty()).kind, 'no_data')
        self.assertEqual(parse_packet(empty(2)).kind, 'busy')
        for flags in (0, 2):
            for offset in (7, 8, 12, 13, 14, 15, 20, 24, 28, 32, 59):
                p = bytearray(empty(flags)); p[offset] = 1
                with self.assertRaises(PacketError): parse_packet(seal(p))

    def test_envelope_rejections(self):
        for bad in (b'', bytes(63), bytes(65), packet()[:-1]):
            with self.assertRaises(PacketError): parse_packet(bad)
        for offset in (0, 3, 4, 5, *range(33, 60)):
            p = bytearray(packet()); p[offset] ^= 1
            with self.assertRaises(PacketError): parse_packet(seal(p))
        p = bytearray(packet()); p[20] ^= 1
        with self.assertRaisesRegex(PacketError, 'CRC'): parse_packet(p)

    def test_unknown_flags_inactive_metadata(self):
        for flags in (1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 128):
            with self.assertRaises(PacketError): parse_packet(packet(flags=flags))
        p = bytearray(packet()); p[7] = 2
        with self.assertRaises(PacketError): parse_packet(seal(p))
        for change in ({'decimals':5}, {'special':10}, {'unit':14}, {'unit':255},
                       {'value':float('nan')}, {'value':float('inf')}, {'value':-float('inf')}):
            with self.assertRaises(PacketError): parse_packet(packet(**change))

    def test_relative_nonzero_flag(self):
        p = bytearray(packet()); p[32] = 255
        self.assertTrue(parse_packet(seal(p)).relative)

    def test_duplicate_does_not_refresh(self):
        t = Freshness(max_age=1)
        self.assertEqual(t.accept(packet(seq=0), 0.9)['state'], 'awaiting_new_sample')
        self.assertEqual(t.accept(packet(), 1)['value'], 1.25)
        self.assertEqual(t.accept(packet(), 1.9)['state'], 'numeric')
        self.assertEqual(t.accept(packet(), 2)['state'], 'stale')
        self.assertIsNone(t.view(2.1)['value'])
        self.assertEqual(t.accept(packet(seq=2), 2.2)['state'], 'numeric')

    def test_counter_wrap_zero_valid(self):
        t = Freshness()
        for seq, now in ((0xfffffffe,1), (0xffffffff,2), (0,3), (1,4)):
            r = t.accept(packet(seq=seq), now)
            expected = 'awaiting_new_sample' if now == 1 else 'numeric'
            self.assertEqual((r['state'], r['sequence'], r['age_seconds']), (expected,seq,0))

    def test_replay_and_conflicting_duplicate_clear_display(self):
        t = Freshness()
        for bad in (packet(seq=19), packet(seq=20,value=2), packet(seq=0x80000014)):
            t.disconnect(); t.accept(packet(seq=20), 0)
            with self.assertRaises(PacketError): t.accept(bad, 0.1)
            self.assertIsNone(t.view(0.1)['value'])

    def test_disconnect_resets_counter_epoch(self):
        t = Freshness(); t.accept(packet(seq=100), 0); t.disconnect()
        self.assertEqual(t.view(1)['state'], 'disconnected')
        self.assertEqual(t.accept(packet(seq=0), 2)['state'], 'awaiting_new_sample')
        self.assertEqual(t.accept(packet(seq=1), 2.1)['state'], 'numeric')

    def test_nonnumeric_and_busy_remove_live_number(self):
        t = Freshness(); t.accept(packet(), 0)
        for p in (packet(seq=2, special=2), packet(seq=3,flags=12), empty(2), empty()):
            self.assertIsNone(t.accept(p,0.1)['value'])

    def test_invalid_packet_clears_live_number(self):
        t = Freshness(); t.accept(packet(),0)
        with self.assertRaises(PacketError): t.accept(b'bad',0.1)
        self.assertEqual(t.view(0.1)['state'],'invalid')
        self.assertIsNone(t.view(0.1)['value'])

    def test_clock_and_configuration(self):
        for age in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError): Freshness(max_age=age)
        t = Freshness(); t.accept(packet(),1)
        with self.assertRaises(ValueError): t.view(0)
        self.assertIsNone(t.view(2)['value'])

    def test_old_snapshot_on_reconnect_requires_counter_advance(self):
        t = Freshness(max_age=1)
        t.accept(packet(seq=70), 0)
        self.assertEqual(t.accept(packet(seq=71), 0.1)['state'], 'numeric')
        t.disconnect()
        first = t.accept(packet(seq=71), 10)
        self.assertEqual(first['state'], 'awaiting_new_sample')
        self.assertIsNone(first['value'])
        self.assertEqual(t.accept(packet(seq=71), 10.5)['age_seconds'], 0.5)
        self.assertEqual(t.accept(packet(seq=71), 11)['state'], 'stale')
        self.assertIsNone(t.view(11)['value'])
        self.assertEqual(t.accept(packet(seq=72), 11.1)['state'], 'numeric')

    def test_baseline_suppresses_status_and_busy_does_not_establish_it(self):
        t = Freshness(max_age=1)
        for p in (empty(2), empty()):
            self.assertIsNone(t.accept(p, 0)['age_seconds'])
        first = t.accept(packet(seq=9, special=2), 1)
        self.assertEqual(first['state'], 'awaiting_new_sample')
        self.assertIsNone(first['display'])
        self.assertEqual(t.accept(packet(seq=10,special=2), 1.1)['display'], '.OL')

    def test_replay_reset_requires_new_baseline_and_advance(self):
        t = Freshness()
        t.accept(packet(seq=50), 0); t.accept(packet(seq=51), 0.1)
        with self.assertRaises(PacketError): t.accept(packet(seq=49), 0.2)
        first = t.accept(packet(seq=49), 0.3)
        self.assertEqual(first['state'], 'awaiting_new_sample')
        self.assertIsNone(first['value'])
        self.assertEqual(t.accept(packet(seq=50), 0.4)['state'], 'numeric')

    def test_generation_change_resets_unchanged_or_restarted_counter(self):
        for restarted in (0, 101):
            t = Freshness(max_age=1)
            t.accept(packet(seq=100, generation=6), 0)
            self.assertEqual(t.accept(packet(seq=101, generation=6), 0.1)['state'], 'numeric')
            baseline = t.accept(packet(seq=restarted, generation=8), 1)
            self.assertEqual((baseline['state'], baseline['generation']), ('awaiting_new_sample', 8))
            self.assertIsNone(baseline['value'])
            self.assertEqual(t.accept(packet(seq=restarted, generation=8), 2)['state'], 'stale')
            self.assertEqual(t.accept(packet(seq=restarted+1, generation=8), 2.1)['state'], 'numeric')

    def test_generation_rollover_and_restart_require_new_sample(self):
        t = Freshness()
        t.accept(packet(seq=9, generation=0xfffffffc), 0)
        t.accept(packet(seq=10, generation=0xfffffffc), 0.1)
        for generation, now in ((0xfffffffe,1), (0,2), (54,3), (0,4)):
            r = t.accept(packet(seq=10, generation=generation), now)
            self.assertEqual(r['state'], 'awaiting_new_sample')
            self.assertIsNone(r['value'])
            self.assertEqual(t.accept(packet(seq=11, generation=generation), now+0.1)['state'], 'numeric')

    def test_odd_generation_transition_never_emits_or_establishes_baseline(self):
        t = Freshness()
        for seq in (100, 101):
            r = t.accept(packet(seq=seq, generation=1), 0)
            self.assertEqual(r['state'], 'transition')
            self.assertIsNone(r['value'])
            self.assertIsNone(r['display'])
            self.assertIsNone(r['sequence'])
            self.assertIsNone(r['age_seconds'])
        baseline = t.accept(packet(seq=102, generation=2), 1)
        self.assertEqual(baseline['state'], 'awaiting_new_sample')
        self.assertEqual(t.accept(packet(seq=103, generation=2), 1.1)['state'], 'numeric')
        transition = t.accept(packet(seq=104, generation=3, special=2), 1.2)
        self.assertEqual(transition['state'], 'transition')
        self.assertIsNone(transition['display'])
        # Even a return to the previous generation cannot revive an old number.
        self.assertEqual(t.accept(packet(seq=103, generation=2), 1.3)['state'], 'awaiting_new_sample')
        self.assertIsNone(t.view(1.3)['value'])
        self.assertEqual(t.accept(packet(seq=104, generation=2), 1.4)['state'], 'numeric')

    def test_same_generation_conflicting_payload_is_rejected(self):
        t = Freshness()
        t.accept(packet(seq=1,generation=42),0)
        t.accept(packet(seq=2,generation=42),0.1)
        with self.assertRaises(PacketError):
            t.accept(packet(seq=2,generation=42,value=99),0.2)
        self.assertIsNone(t.view(0.2)['value'])

    def test_json_stream_and_truncation(self):
        out = io.StringIO()
        decode_stream(io.BytesIO(packet() + packet(seq=2,special=2)), out,
                      Freshness(clock=lambda:0))
        rows = [json.loads(s) for s in out.getvalue().splitlines()]
        self.assertIsNone(rows[0]['value'])
        self.assertEqual(rows[0]['state'], 'awaiting_new_sample')
        self.assertEqual(rows[1]['display'],'.OL')
        self.assertIsNone(rows[1]['value'])
        with self.assertRaises(PacketError): decode_stream(io.BytesIO(packet()[:-1]),io.StringIO())


if __name__ == '__main__':
    unittest.main(verbosity=2)
