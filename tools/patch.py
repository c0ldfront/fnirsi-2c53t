#!/usr/bin/env python3
"""Apply or reverse hash-pinned offline binary edits and optional payload append."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def appended(plan):
    if plan.get('schema') == 1:
        if 'append' in plan:
            raise ValueError('append requires schema 2')
        return b''
    if plan.get('schema') != 2:
        raise ValueError('unsupported plan schema')
    item = plan['append']
    payload = bytes.fromhex(item['hex'])
    if not payload or not isinstance(item.get('reason'), str) or not item['reason'].strip():
        raise ValueError('append requires nonempty bytes and reason')
    if type(item.get('offset')) is not int or item['offset'] != plan['input_size']:
        raise ValueError('append must start exactly at original end')
    if hashlib.sha256(payload).hexdigest() != item.get('sha256'):
        raise ValueError('append hash mismatch')
    if type(plan.get('output_size')) is not int or plan['output_size'] != plan['input_size'] + len(payload):
        raise ValueError('output size mismatch')
    return payload


def forward(data, plan):
    digest = hashlib.sha256(data).hexdigest()
    payload = appended(plan)
    if digest != plan.get('input_sha256') or len(data) != plan.get('input_size'):
        raise ValueError('input size/hash does not match plan')
    edits = plan.get('edits')
    if not isinstance(edits, list) or not edits:
        raise ValueError('plan must contain at least one reviewed edit')
    result = bytearray(data)
    occupied = set()
    changes = []
    for edit in edits:
        off = edit['offset']
        if type(off) is not int or off < 0:
            raise ValueError('offset must be a nonnegative integer')
        old, new = bytes.fromhex(edit['expected_hex']), bytes.fromhex(edit['replacement_hex'])
        if not old or len(old) != len(new) or old == new:
            raise ValueError('edits must be nonempty, equal length and change bytes')
        if not isinstance(edit.get('reason'), str) or not edit['reason'].strip():
            raise ValueError('edit requires a reason')
        end = off + len(old)
        if end > len(data) or data[off:end] != old:
            raise ValueError('expected bytes do not match or edit is out of bounds')
        slots = set(range(off, end))
        if slots & occupied:
            raise ValueError('overlapping edits')
        occupied |= slots
        result[off:end] = new
        changes.append({'offset': off, 'length': len(old), 'reason': edit['reason']})
    result.extend(payload)
    output_hash = hashlib.sha256(result).hexdigest()
    if plan['schema'] == 2 and output_hash != plan.get('output_sha256'):
        raise ValueError('final output hash mismatch')
    return bytes(result), {'input_sha256': digest, 'output_sha256': hashlib.sha256(result).hexdigest(),
                           'size': len(result), 'edits': changes,
                           'hardware_verified': False, 'checksum_or_signature_verified': False}


def prepare(source, plan, reverse=False):
    data = source.read_bytes()
    if not reverse:
        result, report = forward(data, plan)
        if plan['schema'] == 2:
            report['append'] = {'offset': plan['input_size'], 'length': len(appended(plan)),
                                'sha256': plan['append']['sha256'], 'reason': plan['append']['reason']}
        return result, report
    payload = appended(plan)
    size = plan['input_size']
    if type(size) is not int or size < 0 or len(data) != size + len(payload):
        raise ValueError('patched input size mismatch')
    if payload and data[size:] != payload:
        raise ValueError('patched append bytes mismatch')
    original = bytearray(data[:size])
    for edit in plan['edits']:
        off = edit['offset']
        old, new = bytes.fromhex(edit['expected_hex']), bytes.fromhex(edit['replacement_hex'])
        if type(off) is not int or off < 0 or off + len(new) > size:
            raise ValueError('reverse edit offset out of bounds')
        if data[off:off+len(new)] != new or len(old) != len(new):
            raise ValueError('patched edit bytes mismatch')
        original[off:off+len(new)] = old
    # Reuse all forward checks: original hash, overlap, nonempty edits and
    # schema2 output hash. Reverse must reproduce this exact patched input.
    reconstructed, _ = forward(bytes(original), plan)
    if reconstructed != data:
        raise ValueError('reverse round-trip mismatch')
    return bytes(original), {'direction': 'reverse', 'input_sha256': hashlib.sha256(data).hexdigest(),
        'output_sha256': hashlib.sha256(original).hexdigest(), 'size': len(original),
        'hardware_verified': False, 'checksum_or_signature_verified': False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('plan', type=Path)
    ap.add_argument('--output', type=Path, help='create-only regular file; omitted means preview')
    ap.add_argument('--reverse', action='store_true', help='verify and reconstruct original bytes from patched input')
    args = ap.parse_args()
    try:
        result, report = prepare(args.input, json.loads(args.plan.read_text()), args.reverse)
        if args.output:
            # O_EXCL also rejects existing symlinks and the input path itself.
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(result)
                f.flush()
                os.fsync(f.fileno())
            report['output'] = str(args.output)
        report['mode'] = 'written' if args.output else 'preview'
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f'firmware-patch: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
