#!/usr/bin/env python3
"""Generate a reviewed offline append plan from a sealed ARM payload build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(argv):
    p = subprocess.run(argv, capture_output=True, text=True)
    if p.returncode:
        raise ValueError(f'{Path(argv[0]).name} failed: {p.stderr.strip()}')
    return p.stdout


def manifest(path, root):
    result = {}
    for line in path.read_text().splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('invalid hash manifest')
        file = root / name
        if sha(file.read_bytes()) != digest:
            raise ValueError(f'build input/output changed: {name}')
        if name in result:
            raise ValueError(f'duplicate manifest path: {name}')
        result[name] = digest
    if not result:
        raise ValueError('empty hash manifest')
    return result


def branches(edits, symbols, prefix):
    """Use GNU Thumb assembler/linker; no handwritten branch bit encoding."""
    result = {}
    with tempfile.TemporaryDirectory(prefix='fnirsi-plan-') as td:
        td = Path(td)
        asm = ['.syntax unified', '.thumb', '.cpu cortex-m4']
        script = ['OUTPUT_FORMAT("elf32-littlearm")', 'OUTPUT_ARCH(arm)', 'SECTIONS {']
        pending = []
        definitions = ['.syntax unified', '.thumb', '.cpu cortex-m4']
        for index, edit in enumerate(edits):
            if 'replacement' in edit:
                continue
            address = int(edit['address'], 16)
            target_name = edit['proposed_target']
            if target_name not in symbols:
                raise ValueError(f'missing hook symbol: {target_name}')
            target = symbols[target_name] & ~1
            section = f'.patch{index}'
            label = f'branch_target_{index}'
            kind = edit['kind']
            mnemonic = 'bl' if kind == 'Thumb BL' else 'b.w'
            if not kind.startswith('Thumb B'):
                raise ValueError(f'unsupported patch kind: {kind}')
            old = bytes.fromhex(edit['original'])
            if len(old) not in (4, 6):
                raise ValueError('branch overwrite must cover 4 or 6 reviewed bytes')
            asm += [f'.section {section},"ax",%progbits', '.balign 2',
                    f'.extern {label}', f'{mnemonic} {label}']
            definitions += [f'.global {label}', f'.type {label},%function', f'.thumb_set {label},0x{target|1:x}']
            if len(old) == 6:
                asm.append('nop')
            script.append(f'{section} 0x{address:x} : {{ *({section}) }}')
            pending.append((index, section, address, target, mnemonic, len(old)))
        script.append('}')
        (td/'branches.S').write_text('\n'.join(asm)+'\n')
        (td/'symbols.S').write_text('\n'.join(definitions)+'\n')
        (td/'branches.ld').write_text('\n'.join(script)+'\n')
        run([prefix+'as', '-o', str(td/'branches.o'), str(td/'branches.S')])
        run([prefix+'as', '-o', str(td/'symbols.o'), str(td/'symbols.S')])
        run([prefix+'ld', '--fatal-warnings', '-T', str(td/'branches.ld'),
             str(td/'branches.o'), str(td/'symbols.o'), '-o', str(td/'branches.elf')])
        for index, section, address, target, mnemonic, size in pending:
            raw = td/f'patch{index}.bin'
            run([prefix+'objcopy', '-O', 'binary', '-j', section, str(td/'branches.elf'), str(raw)])
            payload = raw.read_bytes()
            if len(payload) != size:
                raise ValueError('assembler/linker changed overwrite size')
            disasm = run([prefix+'objdump', '-d', '-j', section, str(td/'branches.elf')])
            # Reject veneers or a branch to anything other than the linked hook.
            found = re.search(r'\b(bl|b\.w)\s+([0-9a-f]+)\b', disasm)
            if not found or found[1] != mnemonic or int(found[2], 16) != target:
                raise ValueError(f'branch readback mismatch at {address:#x}')
            result[index] = (payload, disasm.replace(str(td), "<scratch>"))
    return result


def prepare(args):
    build = args.build.resolve()
    out = args.artifacts.resolve()
    contract = json.loads((build/'input-contract.json').read_text())
    if not contract.get('lifecycle_inputs_validated', False):
        raise ValueError('lifecycle code/sites/tests are not yet marked ready for offline plan generation')
    sources = manifest(out/'sources.sha256', build)
    artifacts = manifest(out/'artifacts.sha256', out)
    for required in ('payload.elf', 'payload.bin'):
        if required not in artifacts:
            raise ValueError(f'missing artifact manifest entry: {required}')
    if 'input-contract.json' not in sources or 'payload.ld' not in sources:
        raise ValueError('build source manifest does not include contract/linker')
    data = args.stock.read_bytes()
    if len(data) != contract['input_size'] or sha(data) != contract['input_sha256']:
        raise ValueError('stock size/hash mismatch')
    payload = (out/'payload.bin').read_bytes()
    base, append = int(contract['application_base'], 16), int(contract['append_base'], 16)
    if base + len(data) != append or append + len(payload) > int(contract['append_end_exclusive_design_cap'], 16):
        raise ValueError('append mapping/cap mismatch')
    symbols = {}
    for line in run([args.tool_prefix+'nm', '-n', str(out/'payload.elf')]).splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)
    if symbols.get('__payload_start') != append or symbols.get('__payload_end') != append+len(payload):
        raise ValueError('ELF boundaries disagree with payload.bin')
    with tempfile.TemporaryDirectory(prefix='fnirsi-plan-elfcheck-') as td:
        extracted = Path(td)/'payload.bin'
        run([args.tool_prefix+'objcopy', '-O', 'binary', '-j', '.text',
             '-j', '.ARM.extab', '-j', '.ARM.exidx', str(out/'payload.elf'), str(extracted)])
        if extracted.read_bytes() != payload:
            raise ValueError('payload bytes disagree with linked ELF sections')
    expected_sites = contract['required_reviewed_sites']
    for item in expected_sites:
        if 'replacement' not in item:
            target = symbols.get(item['proposed_target'], 0) & ~1
            if not append <= target < append+len(payload):
                raise ValueError('hook target lies outside appended payload')
    encoded = branches(expected_sites, symbols, args.tool_prefix)
    changed = bytearray(data)
    edits, occupied, disassembly = [], set(), {}
    for index, item in enumerate(expected_sites):
        address, offset = int(item['address'], 16), int(item['file_offset'], 16)
        old = bytes.fromhex(item['original'])
        new = bytes.fromhex(item['replacement']) if 'replacement' in item else encoded[index][0]
        if offset != address-base or data[offset:offset+len(old)] != old or len(new) != len(old):
            raise ValueError(f'offset/old bytes/size mismatch at {address:#x}')
        if old == new or set(range(offset, offset+len(old))) & occupied:
            raise ValueError('unchanged or overlapping edit')
        occupied.update(range(offset, offset+len(old)))
        changed[offset:offset+len(old)] = new
        reason = item.get('reason', item.get('proposed_target', item['kind']))
        edits.append({'offset': offset, 'expected_hex': old.hex(), 'replacement_hex': new.hex(), 'reason': reason})
        if index in encoded:
            disassembly[hex(address)] = encoded[index][1]
    changed.extend(payload)
    return {'schema': 2, 'input_size': len(data), 'input_sha256': sha(data),
            'output_size': len(changed), 'output_sha256': sha(changed), 'edits': edits,
            'append': {'offset': len(data), 'hex': payload.hex(), 'sha256': sha(payload),
                       'reason': 'Experimental parsed telemetry payload; hardware and updater acceptance unverified'},
            'review': {'status': 'offline experimental candidate; not production ready',
                       'source_hashes': sources, 'artifact_hashes': artifacts,
                       'branch_disassembly': disassembly,
                       'hardware_verified': False, 'factory_iap_acceptance_verified': False}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build', type=Path, required=True, help='build directory containing contract/linker')
    ap.add_argument('--artifacts', type=Path, required=True, help='sealed build output directory')
    ap.add_argument('--stock', type=Path, required=True, help='pinned unmodified vendor application')
    ap.add_argument('--tool-prefix', default='arm-none-eabi-', help='GNU ARM binutils prefix/path')
    ap.add_argument('--output', type=Path, help='create-only plan file; omitted prints preview plan')
    args = ap.parse_args()
    try:
        plan = prepare(args)
        text = json.dumps(plan, indent=2)+'\n'
        if args.output:
            fd = os.open(args.output, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(text); f.flush(); os.fsync(f.fileno())
            print(json.dumps({'plan': str(args.output), 'output_sha256': plan['output_sha256'],
                              'status': 'experimental offline only'}))
        else:
            print(text, end='')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f'fnirsi-plan: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
