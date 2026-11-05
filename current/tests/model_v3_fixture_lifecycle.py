"""Only three declared module-fixture roots, retired after EVERY phase passes.

This pytest-only lifecycle helper never changes production census or budgets.
No session-end cleanup: missing reports, skips, xfails and interruption retain
all registered module roots. Other modules and function tmp_path stay untouched.
"""
from pathlib import Path
import json
import os
import shutil
import stat

_DECLARED = {
    "test_model_v3_execution_checkpoint_bridge.py": {
        "committed": "execution-H0-one-real-6x512-CLI-family"},
    "test_model_v3_native_checkpoint_bridge.py": {
        "native": "native_bridge_one_checkpoint",
        "bf16_native": "native_bridge_bf16_one_checkpoint"},
}
_STATES = {}
_NODE_MODULES = {}


def _require(value, message):
    if not value:
        raise ValueError(message)


def _checked_root(base, root, identity=None):
    base, root = Path(base).absolute(), Path(root).absolute()
    _require(root.parent == base and root != base, "Only a directly owned mktemp child may be removed")
    # Do not canonicalize away a forbidden root/ancestor symlink before checking.
    for path in (root, *root.parents):
        info = path.lstat()
        _require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
                 "Fixture root and every ancestor must be ordinary directories")
    resolved_base, resolved_root = base.resolve(strict=True), root.resolve(strict=True)
    _require(resolved_root != resolved_base and resolved_root.parent == resolved_base,
             "Resolved fixture root must remain strictly in this worker basetemp")
    info = root.lstat()
    actual = (info.st_dev, info.st_ino, info.st_uid)
    _require(info.st_uid == os.getuid() and (identity is None or actual == identity),
             "Fixture root ownership/inode was replaced")
    return actual


class _OwnedDirectory:
    def __init__(self, base, root):
        self.base, self.path = Path(base).absolute(), Path(root).absolute()
        self.identity = _checked_root(self.base, self.path)
        self.closed, self.retired = False, False

    def fixture_closed(self):
        # The fixture calls this only after its original resource finalizer succeeds.
        _require(not self.closed and not self.retired, "Fixture finalization is one-shot")
        self.closed = True

    def validate(self):
        _require(not self.retired, "Fixture directory already retired")
        _checked_root(self.base, self.path, self.identity)


class _ModuleLifecycle:
    def __init__(self, expected):
        self.expected = frozenset(expected)
        self.reports, self.directories = {}, []
        self.cleaned = False

    def add_directory(self, owned):
        _require(isinstance(owned, _OwnedDirectory) and not self.cleaned
                 and all(item.path != owned.path for item in self.directories),
                 "Only a fresh explicitly registered fixture root is eligible")
        self.directories.append(owned)

    def record_report(self, nodeid, when, passed, wasxfail=False):
        _require(nodeid in self.expected and when in ("setup", "call", "teardown"),
                 "Unexpected module test report")
        phases = self.reports.setdefault(nodeid, {})
        # Repeated or ambiguous reports are never enough to authorize deletion.
        phases[when] = (passed is True and wasxfail is False and when not in phases)

    def try_cleanup(self):
        if self.cleaned or not self.expected or not self.directories:
            return False
        if any(not item.closed for item in self.directories):
            return False
        if any(set(self.reports.get(nodeid, {})) != {"setup", "call", "teardown"}
               or not all(self.reports[nodeid].values()) for nodeid in self.expected):
            return False
        # Validate the WHOLE deletion set, then open and fstat every original
        # root before deleting anything. All operations below use these fds;
        # a later path substitution can never redirect them to a different root.
        _require(shutil.rmtree.avoids_symlink_attacks, "Safe descriptor-based rmtree required")
        for owned in self.directories:
            owned.validate()
        handles = []
        try:
            for owned in self.directories:
                fd = os.open(owned.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                handles.append((owned, fd))
                info = os.fstat(fd)
                _require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                         and (info.st_dev, info.st_ino, info.st_uid) == owned.identity,
                         "Opened fixture inode/owner differs from the registered root")
            for owned, fd in handles:
                with os.scandir(fd) as entries:
                    for entry in entries:
                        if entry.is_dir(follow_symlinks=False):
                            shutil.rmtree(entry.name, dir_fd=fd)
                        else:
                            os.unlink(entry.name, dir_fd=fd)
                _require(not os.listdir(fd), "Fixture root changed during descriptor-bound cleanup")
                # Retain the empty original root. No path-based root rmdir.
                owned.retired = True
                print(json.dumps({"event": "PASSED_MODULE_FIXTURE_CONTENTS_REMOVED_ROOT_RETAINED",
                                  "registered_path": str(owned.path), "opened_dev": owned.identity[0],
                                  "opened_inode": owned.identity[1]}, sort_keys=True), flush=True)
        finally:
            for _, fd in handles:
                os.close(fd)
        self.cleaned = True
        return True


def pytest_collection_modifyitems(items):
    _STATES.clear()
    _NODE_MODULES.clear()
    directory = Path(__file__).resolve().parent
    for item in items:
        path = Path(item.path).absolute()
        if path.name in _DECLARED and path.resolve().parent == directory:
            key = str(path.resolve())
            _NODE_MODULES[item.nodeid] = key
            _STATES.setdefault(key, _ModuleLifecycle(set())).expected |= {item.nodeid}


def own_module_directory(request, tmp_path_factory, prefix):
    module = Path(request.module.__file__).absolute()
    _require(module.name in _DECLARED and module.resolve().parent == Path(__file__).resolve().parent
             and _DECLARED[module.name].get(request.fixturename) == prefix,
             "Only the three declared module fixtures can register a root")
    key = str(module.resolve())
    _require(key in _STATES, "Actual collected module population required before registration")
    base = tmp_path_factory.getbasetemp()
    root = tmp_path_factory.mktemp(prefix)
    owned = _OwnedDirectory(base, root)
    _STATES[key].add_directory(owned)
    return owned


def pytest_runtest_logreport(report):
    key = _NODE_MODULES.get(report.nodeid)
    if key is None:
        return
    state = _STATES[key]
    state.record_report(report.nodeid, report.when, report.passed, hasattr(report, "wasxfail"))
    # The last teardown report is emitted AFTER fixture/module finalizers.
    # A failure/interruption before that point never triggers any cleanup.
    if report.when == "teardown":
        state.try_cleanup()
