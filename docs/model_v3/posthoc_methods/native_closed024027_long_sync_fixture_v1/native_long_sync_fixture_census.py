"""One declared pytest namespace; original production dirfd census otherwise exact."""
import os
from pathlib import Path, PurePosixPath
import re
import stat

FIXTURE_INSERTION = r'''
        # The only exception: this exact metadata pytest namespace. A link is
        # counted as fixture data, never traversed or interpreted as an SDK link.
        if len(relative.parts) > 1 and relative.parts[0] == "metadata_tmp":
            # One lstat snapshot, as in the accepted unit fixture adapter.
            # pytest may replace its current-link atomically; no target is read.
            register(relative, info, links)
            return
'''

def _output_census(root, *, max_entries):
    if os.name != "posix":
        raise ValueError("POSIX dirfd accounting required")
    root = Path(root).absolute()
    if ".." in root.parts:
        raise ValueError("Unsafe output root")
    try:
        initial = root.lstat()
    except FileNotFoundError:
        return 0
    uid = os.getuid()
    if not stat.S_ISDIR(initial.st_mode) or initial.st_uid != uid:
        raise ValueError("Output root must be an owned ordinary directory")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(root, flags)
    counted, paths, regular, links, walked, directory_targets = {}, {}, {}, {}, set(), []
    run_pattern = r"offline-run-[0-9]{8}_[0-9]{6}-[a-z0-9]{8}"
    core_pattern = r"core-debug-[0-9]{8}_[0-9]{6}\.log"

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def owned(info, predicate):
        require(info.st_uid == uid and info.st_dev == initial.st_dev and predicate(info.st_mode),
                "Output UID, device or ordinary type differs")

    def register(relative, info, inventory=None):
        name, key = relative.as_posix(), (info.st_dev, info.st_ino)
        require(name not in paths or paths[name] == key, "Output path changed inode during census")
        paths[name] = key
        require(len(paths) <= max_entries, "Output inode census exceeds entry cap")
        row = counted.setdefault(key, {"bytes": info.st_size, "nlink": info.st_nlink, "mode": stat.S_IFMT(info.st_mode)})
        require(row["mode"] == stat.S_IFMT(info.st_mode), "Output inode type changed")
        row["bytes"], row["nlink"] = max(row["bytes"], info.st_size), max(row["nlink"], info.st_nlink)
        if inventory is not None:
            inventory[name] = key
        return key

    def target_path(relative, text):
        require(text and "\\" not in text and "\0" not in text and len(text) <= 4096, "Unsafe SDK link text")
        pointer = PurePosixPath(text)
        if pointer.is_absolute():
            require(pointer.parts[:len(root.parts)] == root.parts, "SDK link escapes output root")
            components, stack = pointer.parts[len(root.parts):], []
        else:
            components, stack = pointer.parts, list(relative.parent.parts)
        for part in components:
            if part == "..":
                require(bool(stack), "SDK link escapes output root")
                stack.pop()
            elif part not in ("", "."):
                stack.append(part)
        require(stack and len(stack) <= 8, "Unexpected SDK target depth")
        return PurePosixPath(*stack)

    def inspect_target(relative, directory):
        descriptor = os.dup(root_fd)
        prefix = PurePosixPath(".")
        try:
            for part in relative.parts[:-1]:
                try:
                    following = os.open(part, flags, dir_fd=descriptor)
                except FileNotFoundError:
                    return None
                except OSError as exc:
                    raise ValueError("SDK target ancestor is not an ordinary unlinked directory") from exc
                os.close(descriptor)
                descriptor = following
                prefix = prefix / part
                info = os.fstat(descriptor)
                owned(info, stat.S_ISDIR)
                register(prefix, info)
            try:
                info = os.stat(relative.name, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                return None
            owned(info, stat.S_ISDIR if directory else stat.S_ISREG)
            register(relative, info, None if directory else regular)
            return info.st_dev, info.st_ino
        finally:
            os.close(descriptor)

    def check_link(relative, descriptor, name, info):
        owned(info, stat.S_ISLNK)
        # The only exception: this exact metadata pytest namespace. A link is
        # counted as fixture data, never traversed or interpreted as an SDK link.
        if len(relative.parts) > 1 and relative.parts[0] == "metadata_tmp":
            # One lstat snapshot, as in the accepted unit fixture adapter.
            # pytest may replace its current-link atomically; no target is read.
            register(relative, info, links)
            return
        parts = relative.parts
        text = os.readlink(name, dir_fd=descriptor)
        target = target_path(relative, text)
        if parts == ("wandb", "latest-run"):
            require(len(target.parts) == 2 and target.parts[0] == "wandb" and re.fullmatch(run_pattern, target.parts[1]),
                    "Unexpected SDK latest-run target")
            directory = True
        elif len(parts) == 2 and parts[0] == "wandb" and parts[1] in {"debug.log", "debug-internal.log"}:
            require(len(target.parts) == 4 and target.parts[0] == "wandb" and re.fullmatch(run_pattern, target.parts[1])
                    and target.parts[2:] == ("logs", parts[1]), "Unexpected SDK debug-log target")
            directory = False
        else:
            require(len(parts) == 4 and parts[0] == "wandb" and re.fullmatch(run_pattern, parts[1])
                    and parts[2:] == ("logs", "debug-core.log"), "Unexpected output symlink location")
            require(len(target.parts) == 4 and target.parts[:3] == ("cache", "wandb", "logs")
                    and re.fullmatch(core_pattern, target.parts[-1]), "Unexpected SDK debug-core cache target")
            directory = False
        target_key = inspect_target(target, directory)
        current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        require((info.st_dev, info.st_ino, info.st_mode, info.st_uid) ==
                (current.st_dev, current.st_ino, current.st_mode, current.st_uid)
                and os.readlink(name, dir_fd=descriptor) == text, "SDK link changed during census")
        register(relative, current, links)
        if directory and target_key is not None:
            directory_targets.append(target.as_posix())

    try:
        opened = os.fstat(root_fd)
        require((opened.st_dev, opened.st_ino) == (initial.st_dev, initial.st_ino), "Output root changed before open")
        def walk_error(error):
            raise error
        for directory, dirs, files, descriptor in os.fwalk(".", topdown=True, follow_symlinks=False,
                                                          onerror=walk_error, dir_fd=root_fd):
            relative = PurePosixPath(directory)
            info = os.fstat(descriptor)
            owned(info, stat.S_ISDIR)
            register(relative, info)
            walked.add(relative.as_posix())
            for name in tuple(dirs):
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    check_link(relative / name, descriptor, name, info)
                    dirs.remove(name)
                else:
                    owned(info, stat.S_ISDIR)
            for name in files:
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    check_link(relative / name, descriptor, name, info)
                else:
                    owned(info, stat.S_ISREG)
                    register(relative / name, info, regular)
        require(all(target in walked for target in directory_targets), "SDK run target was not independently walked")
        occurrences = {}
        for key in (*regular.values(), *links.values()):
            occurrences[key] = occurrences.get(key, 0) + 1
        require(all(count == counted[key]["nlink"] for key, count in occurrences.items()),
                "Output inode has an external or changed hard link")
        final = root.lstat()
        require(stat.S_ISDIR(final.st_mode) and final.st_uid == uid and
                (final.st_dev, final.st_ino) == (initial.st_dev, initial.st_ino), "Output root changed during census")
        return sum(row["bytes"] for row in counted.values())
    finally:
        os.close(root_fd)


def owned_output_bytes(root, *, max_entries=50000):
    for attempt in range(3):
        try:
            return _output_census(root,max_entries=max_entries)
        except FileNotFoundError:
            if attempt == 2: raise


def verify_derivation(original_source):
    original=Path(original_source).read_text(encoding='utf-8')
    start=original.index('def _output_census(root, *, max_entries):')
    end=original.index('\ndef query(',start)
    old=original[start:end].rstrip()+'\n'
    needle='    def check_link(relative, descriptor, name, info):\n        owned(info, stat.S_ISLNK)\n'
    if old.count(needle) != 1: raise ValueError('Original unique census insertion point changed')
    expected=old.replace(needle,needle+FIXTURE_INSERTION.lstrip('\n'))
    own=Path(__file__).read_text(encoding='utf-8')
    a=own.index('def _output_census(root, *, max_entries):')
    b=own.index('\n\n\ndef owned_output_bytes(',a)
    if own[a:b].rstrip()+'\n' != expected: raise ValueError('Census must be exact original plus metadata-only insertion')
