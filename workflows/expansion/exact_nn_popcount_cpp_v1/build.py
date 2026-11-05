"""Explicit SOURCE-ONLY build recipe; run later only in Root-admitted Linux allocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import sysconfig
from ..exact_nn_cached_v1 import engine as oracle
from . import IMPLEMENTATION
from .artifacts import need, reference, write_new
from .backend import MODULE, SOURCES, BUILD_SCHEMA, BUILD_STATUS

FLAGS = ('-O3', '-std=c11', '-fPIC', '-shared', '-fno-fast-math',
    '-fno-unsafe-math-optimizations', '-fno-reciprocal-math', '-ffp-contract=off', '-Wall', '-Wextra')
PROBE = """import importlib.util,json,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('_ecfp4_popcount_kernel_v1',sys.argv[1])
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
paths=sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
    if len(line.split())>=6 and 'x' in line.split()[1] and line.split()[-1].startswith('/')})
print(json.dumps(dict(kernel=m.build_info(),loaded_executable_files=paths),sort_keys=True))
"""


def cpu_observation():
    fields = {}; raw = Path('/proc/cpuinfo').read_bytes()
    for line in raw.decode().splitlines():
        if ':' in line:
            key, value = (x.strip() for x in line.split(':', 1))
            if key in ('vendor_id', 'model name', 'flags') and key not in fields: fields[key] = value
    return dict(machine=platform.machine(), hostname=socket.gethostname(), cpuinfo_first_values=fields,
        affinity=sorted(os.sched_getaffinity(0)), whole_cpuinfo_sha256=hashlib.sha256(raw).hexdigest())


def build(compiler, output):
    need(sys.platform.startswith('linux') and sys.flags.isolated and sys.flags.dont_write_bytecode
        and os.environ.get('SLURM_JOB_ID') and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) > 0
        and not os.environ.get('SLURM_JOB_GPUS') and not os.environ.get('SLURM_STEP_GPUS'),
        'Explicit Linux Python-I-B build only; never auto-build on import')
    compiler = Path(compiler)
    need(compiler.is_absolute(), 'Root must select an absolute actual C compiler')
    compiler = compiler.resolve(strict=True)
    output = Path(output)
    need(output.is_absolute() and not output.exists(), 'Fresh private absolute build output required')
    package = Path(__file__).parent
    sources = [reference(package / name) for name in SOURCES]
    compiler_ref = reference(compiler, owned=False)
    original_ref = reference(oracle.__file__)
    output.mkdir(parents=True, mode=0o700)
    include = sorted({sysconfig.get_path('include'), sysconfig.get_path('platinclude')} - {None})
    need(include and all(Path(p).is_absolute() for p in include), 'Actual matching CPython development headers required')
    suffix = sysconfig.get_config_var('EXT_SUFFIX'); need(suffix and suffix.endswith('.so'), 'Native Linux CPython extension suffix required')
    binary = output / (MODULE + suffix)
    command = [str(compiler), *FLAGS, *(x for p in include for x in ('-I', p)), str(package / 'kernel.c'), '-o', str(binary)]
    version = subprocess.run([str(compiler), '--version'], capture_output=True, check=True)
    (output / 'compiler_version.stdout').write_bytes(version.stdout)
    (output / 'compiler_version.stderr').write_bytes(version.stderr)
    completed = subprocess.run(command, capture_output=True, check=False)
    (output / 'build.stdout').write_bytes(completed.stdout); (output / 'build.stderr').write_bytes(completed.stderr)
    attempt = dict(schema='EXACT_POPCOUNT_PROTOTYPE_BUILD_ATTEMPT_V1', implementation=IMPLEMENTATION,
        compiler_reference=compiler_ref, compile_argv=command, returncode=completed.returncode,
        source_references=sources, oracle_source_reference=original_ref,
        environment_observed={k: os.environ.get(k) for k in ('CPATH','C_INCLUDE_PATH','LIBRARY_PATH','GCC_EXEC_PREFIX','COMPILER_PATH','LD_LIBRARY_PATH','LD_PRELOAD')})
    write_new(output / 'build_attempt.json', attempt)
    need(completed.returncode == 0, 'Actual native compiler failed; keep failed attempt/logs, no complete build manifest')
    need([reference(package / name) for name in SOURCES] == sources
        and reference(oracle.__file__) == original_ref and reference(compiler, owned=False) == compiler_ref,
        'Scientific/build/compiler source changed during compilation')
    binary_ref = reference(binary)
    probe = subprocess.run([sys.executable, '-I', '-B', '-c', PROBE, str(binary)], capture_output=True, check=False)
    (output / 'probe.stdout').write_bytes(probe.stdout); (output / 'probe.stderr').write_bytes(probe.stderr)
    need(probe.returncode == 0, 'Actual binary metadata import failed; no native equivalence claimed')
    observation = json.loads(probe.stdout); info = observation['kernel']
    libraries = [reference(p, owned=False) for p in observation['loaded_executable_files']]
    need(info['implementation'] == IMPLEMENTATION and info['width_bytes'] == 256 and info['uint64_bytes'] == 8,
        'New prototype native identity/width differs')
    need(reference(binary) == binary_ref, 'Actual binary changed during metadata probe')
    manifest = dict(schema=BUILD_SCHEMA, status=BUILD_STATUS, implementation=IMPLEMENTATION, module_name=MODULE,
        scientific_production_adopted=False, equivalence_or_performance_validated=False,
        binary_reference=binary_ref, source_references=sources, oracle_source_reference=original_ref,
        math_algorithm=oracle.ALGORITHM, fingerprint_recipe=oracle.RECIPE,
        python=dict(executable=sys.executable, version=sys.version, cache_tag=sys.implementation.cache_tag,
            soabi=sysconfig.get_config_var('SOABI'), extension_suffix=suffix, include_directories=include),
        compiler_reference=compiler_ref, compiler_version_reference=reference(output/'compiler_version.stdout'),
        compile_flags=list(FLAGS), compile_argv=command, cpu_observation=cpu_observation(),
        runtime_kernel_info=info, probe_loaded_executable_file_references=libraries, build_attempt_reference=reference(output/'build_attempt.json'),
        logs=[reference(output/name) for name in ('build.stdout','build.stderr','probe.stdout','probe.stderr')],
        actual_uid=os.getuid(), actual_Slurm_job_id=os.environ.get('SLURM_JOB_ID'),
        build_does_not_create_allocation_or_quota_authority=True)
    result = write_new(output / 'build_manifest.json', manifest)
    print(json.dumps(result, sort_keys=True), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); build(args.compiler, args.output)


if __name__ == '__main__':
    main()
