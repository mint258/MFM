"""Declarative copy locators; bytes/SHA are verified only by the admitted reader."""
import pathlib

from portable_n1_source_remaining_v1 import contract as C


ROOT = C.MAIN / 'artifacts/conformers/portable_n1_source_return_import_v1'
ALPHA_OUTPUT = C.ALPHA / 'outputs/portable_n1_source_remaining_v1/export17'
ALPHA_CLAIMS = C.ALPHA / 'artifacts/portable_n1_source_remaining_v1/native_claims'


def path(value):
    C.need(type(value) is str and value.startswith('/') and '\\' not in value,
           'ABSOLUTE_POSIX_RETURN_LOCATOR')
    p = pathlib.PurePosixPath(value)
    C.need(str(p) == value and '..' not in p.parts and p.root == '/',
           'CANONICAL_RETURN_PATH_WITHOUT_ESCAPE')
    return p


class ReturnPaths:
    def __init__(self, plan, manifest):
        self.copy_root = C.literal(str(path(plan['return_copy_directory'])))
        C.need(ROOT in self.copy_root.parents and self.copy_root.is_dir(),
               'EXISTING_OWN_NEW_RETURN_COPY_DIRECTORY')
        shards = {s['shard_id']: s for s in manifest['shards']}
        C.need(set(shards) == {'alpha64', 'alpha16'}, 'ONLY_ORIGINAL_TWO_ALPHA_SHARDS')
        expected = {}
        for sid, shard in shards.items():
            origin = ALPHA_OUTPUT / sid
            C.endpoint(shard['endpoint'])
            C.need(shard['output_directory'] == str(origin) and
                   shard['endpoint']['id'] == 'alpha', 'FROZEN_ORIGINAL_ALPHA_OUTPUT_PREFIX')
            expected[str(origin)] = str(self.copy_root / 'export17' / sid)
        expected[str(ALPHA_CLAIMS)] = str(self.copy_root / 'native_claims')
        self.prefixes = {}
        for item in plan['source_prefix_mappings']:
            C.need(set(item) == {'source_prefix', 'target_prefix'}, 'EXACT_PREFIX_MAPPING_FIELDS')
            origin, target = path(item['source_prefix']), path(item['target_prefix'])
            C.need(str(origin) not in self.prefixes and
                   expected.get(str(origin)) == str(target), 'ONLY_DECLARED_ORIGINAL_RETURN_TREES')
            local = C.literal(str(target))
            C.need(local.is_dir() and self.copy_root in local.parents,
                   'COPIED_PREFIX_EXISTS_WITHOUT_SYMLINK_OR_ESCAPE')
            self.prefixes[str(origin)] = str(local)
        C.need(self.prefixes == expected, 'BOTH_OUTPUT_TREES_AND_NATIVE_CLAIMS_REQUIRED')
        self.exact = plan.get('locator_map', {})
        C.need(type(self.exact) is dict, 'ORIGINAL_EXACT_LOCATOR_DICTIONARY')

    def __call__(self, reference):
        original = C.triple(reference)
        source = path(original['path'])
        exact = self.exact.get(str(source))
        copied = None
        for prefix, target in self.prefixes.items():
            root = path(prefix)
            if root in source.parents:
                relative = source.relative_to(root)
                C.need(relative.parts and '..' not in relative.parts,
                       'RELATIVE_RETURN_FILE_CANNOT_ESCAPE_PREFIX')
                copied = {**original, 'path': str(path(target).joinpath(*relative.parts))}
                if exact is not None:
                    C.need(C.triple(exact) == copied, 'EXACT_AND_PREFIX_COPY_LOCATORS_AGREE')
                break
        if copied is None:
            if exact is not None:
                # Existing exact metadata locators remain usable. Unlisted
                # foreign DATA cannot be introduced through this dictionary.
                C.need(path(str(C.MAIN)) in source.parents or
                       path(str(C.ALPHA / 'control')) in source.parents,
                       'EXACT_FALLBACK_ONLY_MAIN_OR_FOREIGN_CONTROL_METADATA')
                copied = C.triple(exact)
            else:
                C.need(path(str(C.MAIN)) in source.parents,
                       'UNMAPPED_FOREIGN_REFERENCE_HAS_NO_LOCAL_FALLBACK')
                copied = original
        C.need(copied['bytes'] == original['bytes'] and
               copied['sha256'] == original['sha256'], 'EXACT_FOREIGN_COPY_BYTES_UNCHANGED')
        local = C.literal(str(path(copied['path'])))
        C.need(C.MAIN in local.parents, 'ONLY_MAIN_LOCAL_COPY_OR_ORIGINAL_MAIN_REFERENCE')
        return {**original, 'path': str(local)}
