"""Thin mode adapter around the original frozen complete composed fixture.

It changes only explicit builder/bank numeric options, and restores both symbols.
No model/fixture/transform/seed/parameter/acceptance formula is copied or changed.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

from phychem_mfm.model.v3_numeric_stability import COMPENSATED, LEGACY, numeric_mode, validate_numeric_mode

ROOT = Path(__file__).absolute().parents[2]
FIXTURE_SOURCE = Path("/share/home/zixiao/descriptor_analysis/MFM_model_v3_composed_equivariance_runtime_v3/current/phychem_mfm/phase1/v3_composed_equivariance.py")
FIXTURE_SHA256 = "0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8"


def load_equation():
    import phychem_mfm
    if Path(phychem_mfm.__file__).resolve() != (ROOT/"current/phychem_mfm/__init__.py").resolve():
        raise ValueError("Numeric candidate must use its single bound package tree")
    raw = FIXTURE_SOURCE.read_bytes()
    if len(raw) > 64*1024 or hashlib.sha256(raw).hexdigest() != FIXTURE_SHA256:
        raise ValueError("Original frozen composed fixture source differs")
    name = "phychem_mfm.phase1._numeric_stability_original_fixture_v1"
    if name not in sys.modules:
        specification = importlib.util.spec_from_file_location(name, FIXTURE_SOURCE)
        module = importlib.util.module_from_spec(specification)
        sys.modules[name] = module
        try:
            specification.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules[name]


@contextmanager
def composition_mode(equation, mode):
    validate_numeric_mode(mode)
    original_builder, original_bank = equation.build_source_s_architecture_model, equation.V3HeadBank
    def builder(configuration, *args, **kwargs):
        value = deepcopy(configuration)
        if mode == COMPENSATED:
            if "numeric_stability" in value:
                raise ValueError("The frozen fixture already declares another numerical protocol")
            value["numeric_stability"] = {"mode": mode}
        model = original_builder(value, *args, **kwargs)
        if numeric_mode(model) != mode:
            raise ValueError("Actual encoder numeric mode differs")
        return model
    def bank(*args, **kwargs):
        if "numeric_mode" in kwargs:
            raise ValueError("The frozen bank already declares another numeric mode")
        if mode == COMPENSATED:
            kwargs["numeric_mode"] = mode
        value = original_bank(*args, **kwargs)
        if numeric_mode(value) != mode:
            raise ValueError("Actual bank numeric mode differs")
        return value
    equation.build_source_s_architecture_model, equation.V3HeadBank = builder, bank
    try:
        yield
    finally:
        equation.build_source_s_architecture_model, equation.V3HeadBank = original_builder, original_bank


def durable_file(path):
    with Path(path).open("rb") as handle:
        os.fsync(handle.fileno())
    descriptor = os.open(str(Path(path).parent), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
