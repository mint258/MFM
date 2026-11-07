"""One additional readonly native root; original pointer/FD/graph guards remain."""
import pathlib
import types
from workflows.data_v1_final.export.d5_inputs_builder_v1 import reader as OriginalReader
from workflows.data_v1_final.export.family_export_day_v1 import transport as OriginalTransport

PROJECT_ROOT = '/share/home/zixiao/descriptor_analysis'
READONLY_DATASET_ROOT = '/share/home/zixiao/dataset/lmdb_new'
READER_MODULE = 'workflows.data_v1_final.export.d5_inputs_builder_v1.reader'
PRIVATE_READER_MODULE = 'workflows.data_v1_final.export.pilot_D5_parallel_guide_v1.native_io'
_EXTERNAL_READER = None
_NATIVE_BONDS = None


def native_record(pointer, native):
    """Use the declared frozen pointer unchanged, selecting only its valid root."""
    global _EXTERNAL_READER
    path = pathlib.Path(pointer['source_path'])
    if pathlib.Path(READONLY_DATASET_ROOT) not in path.parents:
        return OriginalReader.native_record(pointer, native)
    if _EXTERNAL_READER is None:
        original = OriginalReader.native_record
        code = original.__code__
        OriginalReader.C.need(code.co_consts.count(PROJECT_ROOT) == 1, 'EXACT_ORIGINAL_NATIVE_ROOT_BINDING')
        code = code.replace(co_consts=tuple(READONLY_DATASET_ROOT if value == PROJECT_ROOT else value
                                           for value in code.co_consts))
        _EXTERNAL_READER = types.FunctionType(code, dict(original.__globals__), original.__name__,
                                              original.__defaults__, original.__closure__)
        _EXTERNAL_READER.__kwdefaults__ = original.__kwdefaults__
    # The unchanged original body still rejects '..', every symlink ancestor,
    # nonregular/non-UID1278 files, wrong FD/frame, payload SHA and atom counts.
    return _EXTERNAL_READER(pointer, native)


def native_bonds(pointer, numbers):
    """Original bond transport bytecode with only its local reader import bound."""
    global _NATIVE_BONDS
    if _NATIVE_BONDS is None:
        original = OriginalTransport.native_bonds
        code = original.__code__
        OriginalReader.C.need(code.co_names.count(READER_MODULE) == 1, 'EXACT_ORIGINAL_NATIVE_READER_IMPORT')
        code = code.replace(co_names=tuple(PRIVATE_READER_MODULE if name == READER_MODULE else name
                                          for name in code.co_names))
        _NATIVE_BONDS = types.FunctionType(code, dict(original.__globals__), original.__name__,
                                           original.__defaults__, original.__closure__)
        _NATIVE_BONDS.__kwdefaults__ = original.__kwdefaults__
    return _NATIVE_BONDS(pointer, numbers)
