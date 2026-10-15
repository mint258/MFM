from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import platform
import re
import shutil
import site
import subprocess
import sys
import warnings
from pathlib import Path


TARGET_MODULES = ("pyg_lib", "torch_sparse")
NATIVE_SUFFIXES = (".so", ".dylib", ".pyd", ".dll")
GLIBC_PATTERN = re.compile(r"GLIBC_(\d+)\.(\d+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        "Check whether pyg_lib / torch_sparse can be imported on the current node without starting training."
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        default=list(TARGET_MODULES),
        help="Python extension modules to inspect.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero status if any requested module fails to import.",
    )
    parser.add_argument(
        "--skip-typing-check",
        action="store_true",
        help="Skip importing torch_geometric.typing, which is the place that usually emits the user-facing warnings.",
    )
    return parser.parse_args()


def print_json(prefix: str, payload: dict) -> None:
    print(f"{prefix} {json.dumps(payload, ensure_ascii=True, sort_keys=True)}")


def _parse_glibc_version(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    match = GLIBC_PATTERN.search(text)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def _format_glibc_version(version: tuple[int, int] | None) -> str | None:
    if version is None:
        return None
    return f"{version[0]}.{version[1]}"


def get_host_glibc_version() -> tuple[int, int] | None:
    for getter in (
        lambda: os.confstr("CS_GNU_LIBC_VERSION"),
        lambda: " ".join(platform.libc_ver()),
    ):
        try:
            value = getter()
        except (AttributeError, OSError, ValueError):
            value = None
        parsed = _parse_glibc_version(str(value) if value else None)
        if parsed is not None:
            return parsed
    return None


def run_command(command: list[str]) -> tuple[int | None, str]:
    if not command:
        return None, ""
    if shutil.which(command[0]) is None:
        return None, f"command_not_found: {command[0]}"
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="ignore",
            check=False,
        )
    except Exception as exc:
        return None, repr(exc)
    return int(proc.returncode), proc.stdout


def discover_native_libraries(module_name: str) -> list[Path]:
    candidates: list[Path] = []
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return candidates

    seen: set[Path] = set()

    def maybe_add(path: Path) -> None:
        resolved = path.resolve()
        if resolved.exists() and resolved.suffix in NATIVE_SUFFIXES and resolved not in seen:
            seen.add(resolved)
            candidates.append(resolved)

    if spec.origin:
        maybe_add(Path(spec.origin))

    for location in spec.submodule_search_locations or []:
        root = Path(location)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix in NATIVE_SUFFIXES:
                maybe_add(path)

    if module_name == "pyg_lib":
        extra_roots = [Path(p) for p in site.getsitepackages()]
        extra_roots.append(Path(site.getusersitepackages()))
        for root in extra_roots:
            if not root.exists():
                continue
            for pattern in ("libpyg*.so*", "libpyg*.dylib", "libpyg*.dll"):
                for path in root.glob(pattern):
                    maybe_add(path)

    return candidates


def inspect_native_library(path: Path) -> dict:
    strings_rc, strings_out = run_command(["strings", "-a", str(path)])
    ldd_rc, ldd_out = run_command(["ldd", "-v", str(path)])

    glibc_versions = sorted(
        {
            (int(match.group(1)), int(match.group(2)))
            for match in GLIBC_PATTERN.finditer(strings_out or "")
        }
    )
    return {
        "path": str(path),
        "glibc_versions_found": [_format_glibc_version(item) for item in glibc_versions],
        "max_glibc_found": _format_glibc_version(glibc_versions[-1]) if glibc_versions else None,
        "strings_returncode": strings_rc,
        "ldd_returncode": ldd_rc,
        "ldd_excerpt": (ldd_out or "").splitlines()[:20],
    }


def import_module(module_name: str) -> tuple[bool, str | None]:
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", "unknown")
        return True, str(version)
    except Exception as exc:
        return False, repr(exc)


def inspect_module(module_name: str, host_glibc: tuple[int, int] | None) -> dict:
    spec = importlib.util.find_spec(module_name)
    ok, detail = import_module(module_name)
    native_libs = [inspect_native_library(path) for path in discover_native_libraries(module_name)]

    required_glibc_from_error = None
    if not ok:
        required_glibc_from_error = _parse_glibc_version(detail)

    max_glibc_from_lib = None
    for item in native_libs:
        value = _parse_glibc_version(item.get("max_glibc_found"))
        if value is not None and (max_glibc_from_lib is None or value > max_glibc_from_lib):
            max_glibc_from_lib = value

    inferred_required_glibc = required_glibc_from_error or max_glibc_from_lib
    glibc_mismatch = (
        host_glibc is not None
        and inferred_required_glibc is not None
        and host_glibc < inferred_required_glibc
    )

    return {
        "module": module_name,
        "found": spec is not None,
        "spec_origin": None if spec is None else spec.origin,
        "ok": ok,
        "detail": detail,
        "host_glibc": _format_glibc_version(host_glibc),
        "required_glibc_from_error": _format_glibc_version(required_glibc_from_error),
        "required_glibc_from_binary": _format_glibc_version(max_glibc_from_lib),
        "glibc_mismatch_inferred": bool(glibc_mismatch),
        "native_libraries": native_libs,
    }


def inspect_torch_geometric_typing() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            importlib.import_module("torch_geometric.typing")
            print_json("[TYPING]", {"ok": True})
        except Exception as exc:
            print_json("[TYPING]", {"ok": False, "error": repr(exc)})
        for item in caught:
            print_json(
                "[TYPING_WARNING]",
                {"category": item.category.__name__, "message": str(item.message)},
            )


def main() -> None:
    args = parse_args()

    host_glibc = get_host_glibc_version()
    print_json(
        "[ENV]",
        {
            "python": sys.executable,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "host_glibc": _format_glibc_version(host_glibc),
        },
    )

    try:
        import torch

        print_json(
            "[TORCH]",
            {
                "torch_version": torch.__version__,
                "torch_cuda_version": torch.version.cuda,
                "cuda_available": bool(torch.cuda.is_available()),
                "cuda_device_count": int(torch.cuda.device_count()),
            },
        )
    except Exception as exc:
        print_json("[TORCH]", {"ok": False, "error": repr(exc)})

    try:
        import torch_geometric

        print_json(
            "[PYG]",
            {
                "torch_geometric_version": getattr(torch_geometric, "__version__", "unknown"),
            },
        )
    except Exception as exc:
        print_json("[PYG]", {"ok": False, "error": repr(exc)})

    if not args.skip_typing_check:
        inspect_torch_geometric_typing()

    failures: list[str] = []
    for module_name in args.modules:
        result = inspect_module(module_name, host_glibc)
        print_json("[MODULE]", result)
        if not result["ok"]:
            failures.append(module_name)

    if failures:
        print_json("[SUMMARY]", {"ok": False, "failed_modules": failures})
        if args.strict:
            raise SystemExit(1)
    else:
        print_json("[SUMMARY]", {"ok": True, "failed_modules": []})


if __name__ == "__main__":
    main()
