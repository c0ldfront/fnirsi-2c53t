"""CLI tests with synthetic packets and mocked live connection only."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import cli
from test_parsed import packet
from test_transport import identity, FakeDevice
from transport import Reader


class CliTests(unittest.TestCase):
    def test_offline_defaults_and_invalid_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'capture with spaces.fnp'; p.write_bytes(packet()+packet(seq=2))
            for _ in range(2):
                out=io.StringIO()
                with patch.object(cli,'connect_pyusb',side_effect=AssertionError('unexpected USB')),contextlib.redirect_stdout(out):
                    self.assertEqual(cli.main([str(p)]),0)
                rows=[json.loads(s) for s in out.getvalue().splitlines()]
                self.assertEqual(rows[0]['state'],'awaiting_new_sample')
                self.assertIsNone(rows[0]['value']);self.assertEqual(rows[1]['value'],1.25)
            p.write_bytes(b'bad')
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(cli.main([str(p)]),1)

    def test_live_requires_explicit_selection(self):
        for args in (['--live'],['--vid','0x1234'],['--live','--vid','0x1234']):
            with patch.object(cli,'connect_pyusb',side_effect=AssertionError('unexpected USB')),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:cli.main(args)
                self.assertEqual(error.exception.code,2)

    def test_live_mocked_only_handshake_and_two_reads(self):
        dev=FakeDevice([identity(),packet(),packet(seq=2)])
        reader=Reader(dev);reader.handshake()
        out=io.StringIO()
        with patch.object(cli,'connect_pyusb',return_value=reader) as connect,patch.object(cli.time,'sleep'),contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(['--live','--vid','0x1234','--pid','0xabcd','--count','2']),0)
            connect.assert_called_once_with(0x1234,0xabcd,None)
        rows=[json.loads(s) for s in out.getvalue().splitlines()]
        self.assertEqual(rows[0]['state'],'awaiting_new_sample')
        self.assertEqual(rows[1]['value'],1.25)
        self.assertIn('host_received_at',rows[1]);self.assertTrue(reader._closed)
        self.assertEqual([c[0] for c in dev.calls],[(0xc0,0x50),(0xc0,0x51),(0xc0,0x51)])

if __name__=='__main__':unittest.main(verbosity=2)
