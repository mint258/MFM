"""Use the existing S-prime and D numerical functions without file hashing.

The fixed 30 internal ETKDG candidates, UFF parameters, energy-greedy 0.5 A
selection and maximum three delivered conformers are the established recipe.
SHA in seed_for is the prescribed deterministic seed, not an output checksum.
"""
import importlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import types

from ..uff3_candidate_v1.core import seed_for, IntegrityError
from ..uff3_candidate_v1.native import NativeKernel
from . import stereo


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Kernel(NativeKernel):
    def __init__(self, capsule_path):
        super().__init__()
        manifest = json.loads(Path(capsule_path).read_text())
        roles = {k: Path(v['replica_reference']['path']) for k, v in manifest['roles'].items()}
        sys.path.insert(0, str(roles['science_pin_0'].parent))
        try:
            science = load_module('_window3_original_sprime', roles['science_pin_0'])
        finally:
            sys.path.pop(0)
        science.worker_init()
        package = types.ModuleType('_window3_descriptors')
        package.__path__ = [str(roles['generator'].parent)]
        sys.modules[package.__name__] = package
        generator = importlib.import_module(package.__name__ + '.rdkit_descriptor_generator')
        names = load_module('_window3_D_names', roles['D_names']).D20_NAMES
        funcs = {n: f for n, f, mode in generator.GRAPH_DESCRIPTOR_SPECS if mode == '2d'}
        self._kernels = {'science': science, 'seed_for': lambda mid, retry: seed_for(mid)}
        self.names, self.functions = names, funcs
        self.provenance = {'recipe': 'original_Sprime_fixed30_UFF_max3_no_fill_no_retry'}
        self.old = types.SimpleNamespace(d20=self.d20)
        self.writer = load_module('_window3_family_schema', roles['family_writer'])

    def _graph(self, source):
        from rdkit import Chem
        self.kernels = self._kernels
        self.source_template = Chem.MolFromSmiles(source['isomeric_smiles'])
        if self.source_template is None or Chem.MolToInchiKey(self.source_template) != source['full_key']:
            raise ValueError('SOURCE_FULLKEY_GRAPH_MISMATCH')
        self.template, self.stereo_metadata = stereo.assign(
            self.source_template, molecule_id(source), getattr(self, 'stereo_draw_index', 0))
        self.mol = Chem.AddHs(self.template)
        self.source = source
        self.numbers = [a.GetAtomicNum() for a in self.mol.GetAtoms()]
        self.original_graph = self.kernels['science'].ordered_graph(self.mol)
        return [{'type': str(i.type), 'center': int(i.centeredOn), 'specified': str(i.specified)}
                for i in Chem.FindPotentialStereo(self.mol)
                if str(i.specified) != 'Specified' and self.kernels['science'].stereo_scope(self.mol, i)]

    def prepare_geometry(self, source):
        from rdkit.Chem import AllChem
        unresolved = self._graph(source)
        return dict(D20=None, atomic_numbers=self.numbers, unassigned_stereo=unresolved,
                    uff_supported=bool(AllChem.UFFHasAllMoleculeParams(self.mol)))

    def prepare(self, source):
        prepared = self.prepare_geometry(source)
        # D20 always belongs to the original graph and is calculated once only.
        prepared['D20'], _, _ = self.d20(self.source_template)
        return prepared

    def d20(self, template):
        values, mask, issues = [], [], []
        for name in self.names:
            try:
                value = float(self.functions[name](template))
                valid = math.isfinite(value)
                if not valid: issues.append(name + ':NONFINITE')
            except Exception as exc:
                value, valid = None, False
                issues.append(name + ':' + repr(exc))
            values.append(value if valid else None)
            mask.append(valid)
        return {'names': self.names, 'values': values, 'valid_mask': mask, 'issues': issues}, None, None


def molecule_id(source):
    return 'expansion-pubchem:{pubchem_version}:{cid}:{full_key}'.format(**source)


def select_three(candidates, distance):
    """Identical first-three prefix; unused later candidates need no RMSD.

    All optimized candidates remain in the saved cache for later extensions.
    This is the original energy-greedy >=0.5 A phase, with no fill phase.
    """
    if len({r['candidate_key'] for r in candidates}) != len(candidates):
        raise ValueError('DUPLICATE_CANDIDATE_KEY')
    selected = []
    for row in sorted(candidates, key=lambda r:(r['energy'],r['candidate_key'])):
        closest = min((distance(row, old) for old in selected), default=math.inf)
        if selected and not math.isfinite(closest): raise ValueError('NONFINITE_RMSD')
        if closest >= .5:
            selected.append(dict(row,below_dedup_threshold=False,
                min_rmsd_to_previously_selected_A=None if not selected else closest))
        if len(selected) == 3: break
    return selected


def _generate_once(source, kernel, reuse_d20=False):
    start, cpu = time.monotonic(), time.process_time()
    mid = molecule_id(source)
    packet = {'source': source, 'molecule_id': mid, 'seed': seed_for(mid), 'D20': None,
              'atomic_numbers': [], 'conformers': [], 'candidates': [], 'attempts': [],
              'requested_conformers': 3, 'orders': {'fixed_random': [], 'energy': [], 'diversity': []},
              'state': 'TECHNICAL_UNKNOWN', 'error': None, 'cache_complete': False,
              'candidate_cache_sha256': None, 'atom_order_sha256': None,
              'native_all_failed': False, **stereo.defaults()}
    try:
        prepared = kernel.prepare_geometry(source) if reuse_d20 else kernel.prepare(source)
        packet.update(getattr(kernel, 'stereo_metadata', stereo.defaults()))
        packet['D20'], packet['atomic_numbers'] = prepared['D20'], prepared['atomic_numbers']
        if prepared['unassigned_stereo']:
            packet['state'] = 'STEREO_REFERENCE_UNAVAILABLE_NO_PM7'
        elif not prepared['uff_supported']:
            packet['state'] = 'UFF_UNSUPPORTED'
        else:
            try:
                candidates = [int(c) for c in kernel.embed(packet['seed'], 30)]
            except IntegrityError:
                raise
            except Exception:
                packet['native_all_failed'] = True
                raise
            if len(candidates) > 30 or len(set(candidates)) != len(candidates):
                raise ValueError('INVALID_NATIVE_CANDIDATE_IDS')
            for cid in candidates:
                try:
                    row = kernel.optimize(cid)
                    row['candidate_key'] = 'generated:%06d' % cid
                    valid = row['optimizer_code'] == 0 and row['stereo_valid'] and math.isfinite(row['energy'])
                    packet['attempts'].append({'candidate_id': cid, 'state': 'SUCCESS' if valid else 'NATIVE_REJECTED'})
                    if valid: packet['candidates'].append(row)
                except IntegrityError:
                    raise
                except Exception as exc:
                    packet['attempts'].append({'candidate_id': cid, 'state': 'NATIVE_FAILED', 'error': repr(exc)})
            selected = select_three(packet['candidates'], kernel.distance)
            packet['native_all_failed'] = not packet['candidates']
            for index, row in enumerate(selected[:3]):
                row = dict(row, conformer_id=index, geometry_sha256=None)
                try:
                    row['D3'], row['D3_issues'] = kernel.d3(row)
                except Exception as exc:
                    row['D3'] = {k: None for k in ('PMI1', 'PMI2', 'PMI3', 'PBF_A', 'volume_A3', 'SASA_total_A2', 'SASA_atom_A2')}
                    row['D3_issues'] = [repr(exc)]
                packet['conformers'].append(row)
            packet['state'] = ('EMBED_FAILED' if not candidates else 'SUCCESS' if len(selected) >= 3
                               else 'INSUFFICIENT_UNIQUE_CONFORMERS')
            # Preserve generation order. Other orderings are unnecessary for this
            # candidate delivery and can be derived by the future format exporter.
            packet['orders']['energy'] = list(range(len(packet['conformers'])))
        packet['cache_complete'] = True
    except Exception as exc:
        packet['error'] = type(exc).__name__ + ': ' + str(exc)
        if isinstance(exc, IntegrityError):
            packet['conformers'] = []
            packet['state'] = 'SOURCE_INTEGRITY_HOLD'
    packet['insufficient_conformers'] = len(packet['conformers']) < 3
    packet['generation_order'] = list(range(len(packet['conformers'])))
    packet['worker_wall_seconds'] = time.monotonic() - start
    packet['worker_CPU_seconds'] = time.process_time() - cpu
    return packet


def generate(source, kernel, reuse_d20=False):
    """One native recipe per draw; only all-native-failed stereo draws repeat."""
    began, cpu = time.monotonic(), time.process_time()
    draws, d20 = [], None
    for index in range(stereo.MAX_DRAWS):
        kernel.stereo_draw_index = index
        packet = _generate_once(source, kernel, reuse_d20=reuse_d20 or index > 0)
        if index == 0:
            d20 = packet['D20']
        packet['D20'] = d20
        draws.append({**{k: packet[k] for k in stereo.FIELDS},
                      'state': packet['state'], 'error': packet['error'],
                      'native_all_failed': packet['native_all_failed'],
                      'attempts': packet['attempts'],
                      'assigned_CIP_counts': packet['assigned_CIP_counts'],
                      'assigned_EZ_counts': packet['assigned_EZ_counts']})
        if not stereo.redraw_required(packet):
            break
    packet['stereo_draws'] = draws
    packet['worker_wall_seconds'] = time.monotonic() - began
    packet['worker_CPU_seconds'] = time.process_time() - cpu
    return packet
