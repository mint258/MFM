"""Print existing source-table schemas needed to bind the rotor producer."""
import argparse
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def inspect(root):
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    manifest = json.loads((root/'manifest.json').read_text())
    common = json.loads(Path(manifest['full_source_dependencies']['common']).read_text())
    print(json.dumps(dict(source_dependency_paths=manifest['full_source_dependencies'],
                          common_manifest_keys=sorted(common))), flush=True)
    paths = [Path(ref['path']) for ref in common['membership_tables']]
    paths += [Path(directory)/'id_map.parquet' for directory in manifest['split_roots'].values()]
    for path in paths:
        with pq.ParquetFile(path) as table:
            print(json.dumps(dict(path=str(path), schema=str(table.schema_arrow))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    inspect(parser.parse_args().root)
