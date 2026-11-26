"""Future collector segments retain the original physical write guard.

The already running canonical entry and its source remain unchanged. Its exact
predecessor/deadline/collection-lock and scientific entry are reused here.
"""
from . import reference_segment_canonical
from .reference_runtime_storage import scoped_physical_writes


def main():
    previous = reference_segment_canonical.scoped_collector_writes
    try:
        reference_segment_canonical.scoped_collector_writes = scoped_physical_writes
        return reference_segment_canonical.main()
    finally:
        reference_segment_canonical.scoped_collector_writes = previous


if __name__ == "__main__":
    raise SystemExit(main())
