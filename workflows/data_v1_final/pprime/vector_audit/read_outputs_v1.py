"""Small, independent raw-coordinate/vector readers; frozen parsers stay unchanged."""
from __future__ import annotations

import json
import re

from math_v1 import FLOAT, rounding_halfwidth, BOHR_TO_A, AU_DIPOLE_TO_DEBYE


def numbers(tokens):
    values = [float(token.replace('D', 'E').replace('d', 'e')) for token in tokens]
    return values, [rounding_halfwidth(token) for token in tokens]


def aux_arrays(text, natoms):
    wanted = {'ATOM_EL', 'ATOM_X_OPT:ANGSTROMS', 'DIP_VEC:DEBYE',
              'GRADIENTS:KCAL/MOL/ANGSTROM'}
    header = re.compile(r'^\s*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?\s*=\s*(.*)$')
    found, active, tokens, expected = {}, None, [], None
    def finish():
        if active is None:
            return
        if expected is None or len(tokens) != expected:
            raise ValueError('AUDIT_AUX_EXACT_COUNT_REQUIRED:' + active)
        if active == 'ATOM_EL':
            found[active] = {'values': [t.strip('"\'') for t in tokens]}
        else:
            vals, eps = numbers(tokens)
            found[active] = {'values': vals, 'rounding_halfwidth': eps}
    for line in text.splitlines():
        match = header.match(line)
        if match:
            finish()
            key, count, tail = match.groups()
            active = key.strip() if key.strip() in wanted else None
            expected = int(count) if count is not None else None
            tokens = (tail.split() if active == 'ATOM_EL' else re.findall(FLOAT, tail)) if active else []
        elif active and not line.lstrip().startswith('#'):
            tokens.extend(line.split() if active == 'ATOM_EL' else re.findall(FLOAT, line))
    finish()
    for key in ('ATOM_X_OPT:ANGSTROMS', 'GRADIENTS:KCAL/MOL/ANGSTROM'):
        if key in found:
            if len(found[key]['values']) != 3*natoms:
                raise ValueError('AUX_VECTOR_OR_COORDINATE_NOT_3N:' + key)
            for part in ('values', 'rounding_halfwidth'):
                flat = found[key][part]
                found[key][part] = [flat[i:i+3] for i in range(0, len(flat), 3)]
    return found


def xtb_gradient(text, symbols):
    rows = [line.split() for line in text.splitlines()]
    coordinate = [r for r in rows if len(r) == 4 and r[-1].capitalize() in symbols]
    vector = [r for r in rows if len(r) == 3 and all(re.fullmatch(FLOAT, v) for v in r)]
    if len(coordinate) != len(symbols) or len(vector) != len(symbols):
        raise ValueError('EXACT_SINGLE_XTB_GRADIENT_BLOCK_REQUIRED')
    if [r[3].capitalize() for r in coordinate] != symbols:
        raise ValueError('XTB_GRADIENT_OUTPUT_ATOM_ORDER_CHANGED')
    xyz, xyz_bohr, eps_xyz, gradient, eps_gradient = [], [], [], [], []
    for row in coordinate:
        values, eps = numbers(row[:3])
        xyz_bohr.append(values)
        xyz.append([v*BOHR_TO_A for v in values])
        eps_xyz.append([v*BOHR_TO_A for v in eps])
    for row in vector:
        values, eps = numbers(row)
        gradient.append(values)
        eps_gradient.append(eps)
    legacy_xyz = [[v*0.52917726 for v in row] for row in xyz_bohr]
    return {'coordinates_A': xyz, 'coordinates_bohr': xyz_bohr,
            'coordinate_conversion_hypotheses_A': {
                'WP5_parser_0.529177210903': xyz, 'xTB_legacy_autoaa_0.52917726': legacy_xyz},
            'coordinate_rounding_halfwidth_A': eps_xyz,
            'gradient_Eh_bohr': gradient, 'gradient_rounding_halfwidth_Eh_bohr': eps_gradient,
            'symbols': list(symbols)}


def xtb_dipole(text):
    raw = json.loads(text)
    hit = re.search(r'"dipole / a\.u\."\s*:\s*\[([^\]]+)\]', text)
    if 'dipole / a.u.' not in raw or hit is None:
        return None
    tokens = re.findall(FLOAT, hit.group(1))
    values, eps = numbers(tokens)
    if len(values) != 3:
        raise ValueError('XTB_DIPOLE_NOT_THREE_COMPONENTS')
    return {'dipole_Debye': [v*AU_DIPOLE_TO_DEBYE for v in values],
            'rounding_halfwidth_Debye': [v*AU_DIPOLE_TO_DEBYE for v in eps],
            'raw_atomic_units': values}


def xtb_quadrupole(text):
    if 'molecular quadrupole (traceless):' not in text:
        return None
    part = text.rsplit('molecular quadrupole (traceless):', 1)[1]
    header = re.search(r'xx\s+xy\s+yy\s+xz\s+yz\s+zz', part)
    full = re.search(r'(?m)^\s*full:\s*(.*)$', part)
    if header is None or full is None:
        raise ValueError('QUADRUPOLE_HEADER_OR_FULL_ROW_NOT_IDENTIFIED')
    tokens = re.findall(FLOAT, full.group(1))
    if len(tokens) != 6:
        raise ValueError('QUADRUPOLE_MUST_KEEP_SIX_FULL_COMPONENTS')
    values, eps = numbers(tokens)
    return {'six_components_au': values, 'rounding_halfwidth_au': eps,
            'component_order': ['xx', 'xy', 'yy', 'xz', 'yz', 'zz']}


def parse_outputs(files, task, symbols):
    text = {f['name']: f['data'].decode('utf-8', errors='replace') for f in files}
    result = {'task': task, 'source_output_files': sorted(text)}
    if task == 'pm7_B':
        result['mopac_aux'] = aux_arrays(text.get('input.aux', ''), len(symbols))
    else:
        result['xtb_dipole'] = xtb_dipole(text['xtbout.json']) if 'xtbout.json' in text else None
        result['xtb_gradient'] = xtb_gradient(text['gradient'], symbols) if 'gradient' in text else None
        result['xtb_quadrupole'] = xtb_quadrupole(text.get('process.out', ''))
    return result
