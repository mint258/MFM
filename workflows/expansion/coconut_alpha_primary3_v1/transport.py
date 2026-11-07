"""Explicit OriginWindowsRef -> actualAlphaRef map; no guessed path rewriting."""
import json
from pathlib import Path, PureWindowsPath
from workflows.expansion.coconut_alpha_cached735_v1 import support as S


def triple(ref):
    return {k:ref[k] for k in ('path', 'bytes', 'sha256')}


class Evidence:
    def __init__(self, plan):
        self.map_ref = plan['origin_windows_transport_reference']
        self.manifest_ref = plan['primary_evidence_manifest_reference']
        transport = S.load(self.map_ref)
        S.need(transport['schema'] == 'PUBCHEM_ORIGIN_WINDOWS_SOURCE_REPLICAS_V1'
               and transport['status'] == 'VERIFIED_BYTES_COPIED_NO_SCIENTIFIC_ADMISSION'
               and transport['destination'] == dict(endpoint='218.192.171.238:22', uid=1264),
               'EXPLICIT_REAL_ALPHA_REPLICA_MAP')
        origin = triple(transport['origin_windows_manifest_reference'])
        S.need(PureWindowsPath(origin['path']).is_absolute()
               and {k:origin[k] for k in ('bytes', 'sha256')} ==
               {k:self.manifest_ref[k] for k in ('bytes', 'sha256')}
               and triple(transport['replica_manifest_reference']) == triple(self.manifest_ref),
               'ORIGIN_MANIFEST_BYTES_EXACTLY_REPLICATED_NO_ORIGIN_UID_FABRICATION')
        self.manifest = S.load(self.manifest_ref)
        S.need(self.manifest['schema'] == 'PUBCHEM_SIX_PRIMARY_SOURCE_RECOVERY_RESEARCH_V1'
               and self.manifest['strict5_or_all11_acceptance'] is False
               and self.manifest['chemistry_executed'] is False, 'SOURCE_RESEARCH_NOT_ACCEPTANCE')
        self.origins = {r['path']:triple(r) for r in self.manifest['files']}
        S.need(len(self.origins) == len(self.manifest['files']), 'UNIQUE_ORIGIN_BODY_REFERENCES')
        self.mapping = {}
        for item in transport['replicas']:
            old, new = triple(item['origin_reference']), triple(item['replica_reference'])
            S.need(PureWindowsPath(old['path']).is_absolute() and self.origins.get(old['path']) == old
                   and all(old[k] == new[k] for k in ('bytes', 'sha256'))
                   and Path(new['path']).is_absolute()
                   and Path(new['path']).is_relative_to(Path('/gfshome/alpha')),
                   'EXACT_ORIGIN_TRIPLE_AND_REAL_GF_ALPHA_DESTINATION')
            S.need(old['path'] not in self.mapping, 'NO_DUPLICATE_REPLICA_MAPPING')
            self.mapping[old['path']] = new
        S.need(set(self.mapping) == set(self.origins), 'COMPLETE_EXPLICIT_SOURCE_MAP_NO_PATH_FALLBACK')
        for item in transport.get('supplemental_replicas', []):
            old,new=triple(item['origin_reference']),triple(item['replica_reference'])
            S.need(PureWindowsPath(old['path']).is_absolute() and old['path'] not in self.origins
                   and all(old[k] == new[k] for k in ('bytes','sha256'))
                   and Path(new['path']).is_absolute()
                   and Path(new['path']).is_relative_to(Path('/gfshome/alpha')),
                   'EXPLICIT_SEPARATE_SUPPLEMENTAL_ORIGIN_REPLICA')
            self.origins[old['path']]=old;self.mapping[old['path']]=new
        self.selected = {}

    def origin(self, filename):
        matches = [r for p,r in self.origins.items() if PureWindowsPath(p).name == filename]
        S.need(len(matches) == 1, 'UNIQUE_MANIFEST_BODY_NAME_NOT_AN_IMPLICIT_PATH_REWRITE:' + filename)
        return matches[0]

    def read(self, filename):
        old = self.origin(filename); new = self.mapping[old['path']]
        raw = S.read(new, 64 << 20)
        self.selected[filename] = dict(origin_reference=old, replica_reference=new)
        return raw

    def ref(self, filename):
        old = self.origin(filename)
        return dict(origin_reference=old, replica_reference=self.mapping[old['path']])
