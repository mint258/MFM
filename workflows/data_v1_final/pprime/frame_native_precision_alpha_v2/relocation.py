"""Explicit readonly origin->Alpha locators and frozen-function metadata loader.

Original JSON/source bytes are not rewritten. No old module is imported then
patched for paths: frozen function ASTs are compiled into new isolated namespaces.
"""
from __future__ import annotations
import ast,concurrent.futures as cf,hashlib,json,math,os,pathlib,re,stat,struct,types

MAIN='/share/home/zixiao/descriptor_analysis'
ALPHA=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
REPO=MAIN+'/runs/data_v1_20261025/repository'
PPRIME=REPO+'/workflows/data_v1_final/pprime'
VECTOR=PPRIME+'/vector_audit'
NATIVE=MAIN+'/runs/phase1_dataset_rebuild_20261010/scripts/wp4_native_pilot_v4.py'
WP5=MAIN+'/runs/phase1_wp5_20261011/scripts'
ACTIVE=None


def need(ok,message):
    if not ok:raise ValueError(message)


def actual_ref(path):
    path=pathlib.Path(path).absolute();h=hashlib.sha256()
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode),'REGULAR_ALPHA_COPY_REQUIRED')
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
        after=os.fstat(stream.fileno())
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'ALPHA_COPY_CHANGED_DURING_READBACK')
    linked=path.stat()
    need((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)==
        (linked.st_dev,linked.st_ino,linked.st_size,linked.st_mtime_ns),'ALPHA_COPY_LOCATOR_REPLACED_DURING_READBACK')
    return {'path':str(path),'bytes':before.st_size,'sha256':h.hexdigest()}


class Resolver:
    def __init__(self,map_path):
        self.map_path=pathlib.Path(map_path);self.mapping=json.loads(self.map_path.read_text())
        need(self.mapping.get('schema')=='NATIVE72_READONLY_RELOCATION_MAP_V1','EXPLICIT_NATIVE72_RELOCATION_REQUIRED')
        inventory_path=pathlib.Path(__file__).absolute().parent/'origin_inventory.json'
        need(self.mapping['origin_inventory_reference']==actual_ref(inventory_path),'EXACT_REVIEWED_ORIGIN_INVENTORY_REQUIRED')
        inventory=json.loads(inventory_path.read_text());expected={row['origin']['path']:row for row in inventory['entries']}
        need(len(expected)==len(inventory['entries'])==len(self.mapping['entries']),'COMPLETE_UNIQUE_ORIGIN_RELOCATION_REQUIRED')
        self.origins={};self.targets={};self.verified={}
        for row in self.mapping['entries']:
            origin=row['origin'];target=row['target_reference'];old=origin['path'];new=target['path']
            need(old in expected and origin==expected[old]['origin'] and row['kind']==expected[old]['kind']
                and new==expected[old]['target_locator'] and row.get('origin_stat')==expected[old].get('origin_stat'),
                'ORIGINAL_MANIFEST_OR_ALPHA_LOCATOR_REWRITTEN')
            need(old.startswith(MAIN+'/') and '..' not in pathlib.Path(old).parts and ALPHA in pathlib.Path(new).parents
                and '..' not in pathlib.Path(new).parts and origin['bytes']==target['bytes'],'EXACT_MAIN_TO_ALPHA_LITERAL_BYTES_LOCATORS_REQUIRED')
            need(old not in self.origins and new not in self.targets,'NO_CONFLICTING_OR_ALIAS_RELOCATION')
            if origin.get('sha256') is not None:
                need(set(target)=={'path','bytes','sha256'} and origin['sha256']==target['sha256'],'BYTE_EQUIVALENT_SOURCE_COPY_REQUIRED')
            else:
                need(set(target)=={'path','bytes'} and row['kind'] in {'raw_sqlite_locator_no_main_SHA',
                    'actual_input_stat_locator','prepared_input_stat_locator'},'NO_INVENTED_HISTORICAL_OR_PREOBSERVED_COPY_SHA')
            self.origins[old]=row;self.targets[new]=row
        for kind,count in (('raw_sqlite_locator_no_main_SHA',72),('pinned_case_result_metadata',72),
                ('actual_input_stat_locator',144),('prepared_input_stat_locator',144)):
            need(sum(row['kind']==kind for row in self.origins.values())==count,'EXACT_FROZEN_NATIVE72_DERIVED_AUTHORITY_REQUIRED:'+kind)

    def row(self,path):
        key=str(path);need(key in self.origins or key in self.targets,'UNMAPPED_ORIGIN_OR_TARGET:'+key)
        return self.origins.get(key,self.targets.get(key))

    def path(self,path,verify=False):
        row=self.row(path);target=row['target_reference'];local=pathlib.Path(target['path'])
        need(local.is_file() and not any(p.is_symlink() for p in (local,*local.parents))
            and local.stat().st_size==target['bytes'],'ACTUAL_ALPHA_MAPPED_FILE_REQUIRED')
        if verify:
            observed=actual_ref(local)
            need(all(observed[key]==value for key,value in target.items()),'ACTUAL_ALPHA_TARGET_BYTES_OR_SHA_CHANGED')
            self.verified[target['path']]=observed
        return local

    def require(self,pin,full_hash=True):
        row=self.row(pin['path']);target=row['target_reference']
        need(pin.get('bytes',target['bytes'])==target['bytes'] and
            ('sha256' not in target or pin.get('sha256',target['sha256'])==target['sha256']),'ORIGINAL_PIN_AND_TARGET_COPY_DIFFER')
        path=self.path(pin['path'],verify=full_hash)
        if full_hash and 'sha256' in pin:
            need(self.verified[target['path']]['sha256']==pin['sha256'],'ORIGINAL_TRANSITIVE_SHA_AND_ACTUAL_INPUT_DIFFER')
        return path

    def reference(self,path):
        key=str(path)
        if key not in self.origins and key not in self.targets:return actual_ref(path)
        row=self.row(key);self.path(key,verify=True);origin=row['origin']
        if origin.get('sha256') is not None:return {name:origin[name] for name in ('path','bytes','sha256')}
        # Raw SQLite had no original whole-file SHA. Preserve that fact instead
        # of labeling Alpha's newly measured digest a historical Main digest.
        return {'origin_locator':origin,'origin_stat':row.get('origin_stat'),
            'actual_alpha_reference':self.verified[row['target_reference']['path']],'main_whole_file_SHA_claimed':False,
            'integrity_basis':'original pinned per-call raw SHA/size + gzip EOF/CRC + member SHA; actual Alpha whole-file SHA'}

    def json(self,path):
        need('sha256' in self.row(path)['origin'],'FROZEN_SMALL_JSON_REFERENCE_REQUIRED')
        return json.loads(self.path(path,verify=True).read_text())

    def verify_raw_targets(self,declared):
        rows=[row for row in self.origins.values() if row['kind']=='raw_sqlite_locator_no_main_SHA']
        need(declared==[] and len(rows)==72,'FROZEN_TRANSITIVE_ARCHIVE_AUTHORITY_ONLY_NO_PRETENDED_DATABASE_SHA')
        with cf.ThreadPoolExecutor(max_workers=16) as pool:
            checked=list(pool.map(lambda row:self.path(row['origin']['path'],verify=True),rows))
        return {'actual_alpha_whole_file_SHA_verified':len(checked),'Main_whole_database_SHA_inferred':False,
            'hash_basis':'FROZEN_PER_CALL_SHA_AND_INPUT_METADATA',
            'database_reference_pairs':[{'origin_locator':row['origin'],'actual_alpha_observed_reference':self.verified[row['target_reference']['path']],
                'origin_stat':row.get('origin_stat'),'Main_historical_whole_SHA':None} for row in rows]}


def activate(map_path):
    global ACTIVE
    ACTIVE=Resolver(map_path);return ACTIVE


def require_pin(pin,full_hash=True):return ACTIVE.require(pin,full_hash=full_hash)
def reference(path):return ACTIVE.reference(path)
def resolve(path):return ACTIVE.path(path)


def read_staging(line):
    # Exact original common.read_staging semantics, no JSON path rewriting.
    def hook(v):
        if set(v)=={'__pprime_nonfinite_float64__'}:
            return struct.unpack('<d',bytes.fromhex(v['__pprime_nonfinite_float64__']))[0]
        return v
    return json.loads(line,object_hook=hook)


def declarations(origin,name,bindings=None,omit_names=(),selected_functions=None):
    """Compile unchanged definitions/assignments; omit only path/import bootstrap.

    Hash-verified source remains byte-identical on disk. New namespaces are born
    with their explicit already-loaded dependency objects, not patched old ones.
    """
    path=ACTIVE.path(origin,verify=True);text=path.read_text();tree=ast.parse(text);body=[];function_evidence={}
    for node in tree.body:
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            if selected_functions is None or isinstance(node,ast.ImportFrom) and node.module=='__future__':body.append(node)
        elif isinstance(node,(ast.FunctionDef,ast.ClassDef)):
            if selected_functions is None or node.name in selected_functions:
                body.append(node);function_evidence[node.name]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
        elif isinstance(node,(ast.Assign,ast.AnnAssign)) and selected_functions is None:
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            names={target.id for target in targets if isinstance(target,ast.Name)}
            if not names.intersection(omit_names):body.append(node)
    module=types.ModuleType(name);namespace=module.__dict__
    if selected_functions is not None:need(set(function_evidence)==set(selected_functions),'EXACT_SELECTED_FROZEN_DEFINITIONS_REQUIRED')
    namespace.update({'__file__':str(path),'__name__':name});namespace.update(bindings or {})
    exec(compile(ast.Module(body=body,type_ignores=[]),str(path),'exec'),namespace)
    module._source_evidence={'origin':ACTIVE.row(origin)['origin'],'alpha':ACTIVE.row(origin)['target_reference'],
        'unchanged_function_AST_SHA256':function_evidence,'metadata_bootstrap_omissions':list(omit_names)}
    return module


def load_audit(path):
    import math_v1
    c=ACTIVE.json(path)
    need(c['schema']=='PPRIME_VECTOR_FRAME_AUDIT_V1' and c['maximum_molecules']==4 and c['minimum_molecules']==2,'FROZEN_TWO_TO_FOUR_AUDIT_REQUIRED')
    need(c['rotation_matrix']==math_v1.ROTATION and c['production_membership'] is False,'FROZEN_AUDIT_ROTATION_AND_ISOLATION_REQUIRED')
    math_v1.checked_rotation(c['rotation_matrix'])
    for pin in c['parent_source_pins']:require_pin(pin)
    return c


def metadata_engine(pilot):
    contract=json.loads(require_pin(pilot['legacy_contract']).read_text());protocol=json.loads(require_pin(contract['protocol']).read_text())
    names=('pm7_B','pm7_water','pm7_octanol','pm7_cation','pm7_anion','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
    need(tuple(row['name'] for row in protocol['tasks'])==names and protocol['perturb_sigma_A']==0.1 and protocol['seed']==20261010,'EXACT_ORIGINAL_RECIPE_METADATA_REQUIRED')
    for name in ('wp5_engine_v3.py','wp5_parser_v2.py','wp5_archive_v4.py','wp5_archive_v5.py'):
        refs=[row for row in contract['sources'] if pathlib.Path(row['path']).name==name]
        need(len(refs)==1,'EXACT_ORIGINAL_READONLY_SCIENTIFIC_DEPENDENCY_REQUIRED:'+name);require_pin(refs[0])
    archive=declarations(WP5+'/wp5_archive_v4.py','_alpha_native72_archive',
        bindings={'MAGIC':b'WP5BUNDLE1\0','hashlib':hashlib,'json':json,'struct':struct,'PurePosixPath':pathlib.PurePosixPath},
        selected_functions={'digest','safe_name','unbundle'})
    archive.FORBIDDEN_INPUT_NAMES={'input.xyz','input.mop','native.inp','input_recipe.json'}
    engine=declarations(WP5+'/wp5_engine_v3.py','_alpha_native72_pure_input_renderer',
        bindings={'hashlib':hashlib,'CONFIG':None},selected_functions={'perturb_seed','render_inputs'})
    engine.OUTPUT_ARCHIVE=archive
    return engine,contract,protocol


def parser_and_measurement():
    # Original imports are stdlib. Their path/bootstrap module-execution
    # statements are omitted, while every numerical function AST is unchanged.
    legacy=declarations(MAIN+'/runs/phase1_dataset_rebuild_20261010/scripts/wp4_parsers.py','_alpha_native72_legacy')
    base=declarations(WP5+'/wp5_parser.py','_alpha_native72_base',bindings={'_LEGACY':legacy},
        omit_names={'LEGACY_PATH','LEGACY_SHA','_spec','_LEGACY'})
    parser=declarations(WP5+'/wp5_parser_v2.py','_alpha_native72_parser2',bindings={'_BASE':base},
        omit_names={'BASE_PATH','BASE_SHA','_spec','_BASE'})
    import math_v1 as m
    measurement=declarations(VECTOR+'/evaluate_v1.py','_alpha_native72_measurement',
        bindings={key:getattr(m,key) for key in ('AU_DIPOLE_TO_DEBYE','covariance','force_relation','mechanical_diagnostics',
            'output_frame','tensor_checks','tensor_covariance','tensor_translation')},selected_functions={'compare_stored','measurement'})
    return parser,measurement
