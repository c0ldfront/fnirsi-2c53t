#!/usr/bin/env python3
"""Read FNP1 telemetry files or explicitly requested read-only live USB telemetry."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

from parsed import Freshness, PacketError, decode_stream
from transport import connect_pyusb


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('must be finite and positive')
    return value


def usb_id(value):
    try: value = int(value, 0)
    except ValueError as exc: raise argparse.ArgumentTypeError('use decimal or 0x-prefixed hex') from exc
    if not 0 <= value <= 0xffff:
        raise argparse.ArgumentTypeError('USB identifier must be 0..65535')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', default='-', help='offline FNP1 binary file, or - for stdin (default)')
    parser.add_argument('--live', action='store_true', help='explicitly open one USB device; never flash firmware')
    parser.add_argument('--vid', type=usb_id, help='required with --live; e.g. 0x1234')
    parser.add_argument('--pid', type=usb_id, help='required with --live; e.g. 0x5678')
    parser.add_argument('--serial', help='select an exact serial when VID/PID match multiple devices')
    parser.add_argument('--max-age', type=positive, default=1.0, help='freshness timeout in host seconds (default 1)')
    parser.add_argument('--interval', type=positive, default=None, help='live polling interval seconds (default 0.1)')
    parser.add_argument('--count', type=int, default=None, help='live packet count, 0 means until interrupted (default 0)')
    args = parser.parse_args(argv)
    if args.live:
        if args.input != '-': parser.error('--live cannot also read an offline file')
        if args.vid is None or args.pid is None: parser.error('--live requires --vid and --pid')
        if args.count is not None and args.count < 0: parser.error('--count cannot be negative')
    elif any(v is not None for v in (args.vid,args.pid,args.serial,args.interval,args.count)):
        parser.error('USB selection, --interval and --count require explicit --live')
    reader = None
    try:
        if not args.live:
            tracker = Freshness(max_age=args.max_age)
            if args.input == '-': decode_stream(sys.stdin.buffer, sys.stdout, tracker)
            else:
                with open(args.input, 'rb') as source: decode_stream(source, sys.stdout, tracker)
            return 0
        reader = connect_pyusb(args.vid, args.pid, args.serial)
        # connect_pyusb already validated identity; no packet has been consumed.
        reader.freshness = Freshness(max_age=args.max_age)
        count = 0
        while True:
            result = reader.read()
            result['host_received_at'] = datetime.now(timezone.utc).isoformat()
            print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
            count += 1
            if args.count and count >= args.count: break
            time.sleep(args.interval if args.interval is not None else 0.1)
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'fnirsi-telemetry: {exc}', file=sys.stderr)
        return 1
    finally:
        if reader is not None: reader.close()


if __name__ == '__main__':
    raise SystemExit(main())
