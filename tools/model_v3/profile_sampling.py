"""Fixed diagnostic sampling and separately timed training throughput."""
import math


def representative_steps(steps):
    if type(steps) is not int or not 1 <= steps <= 20:
        raise ValueError('Require 1..20 measured optimizer steps')
    return tuple(sorted({0, steps // 2, steps - 1}))


def throughput_summary(rows):
    if not rows or len({row['ordinal'] for row in rows}) != len(rows):
        raise ValueError('Nonempty unique measured step records required')
    selected = [row for row in rows if not row['profiled']] or list(rows)
    for row in selected:
        value = row['end_to_end_step_seconds']
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Finite positive complete-step timings required')
    duration = sum(row['end_to_end_step_seconds'] for row in selected)
    fields = {'base_structures_per_second': 'base_molecules',
              'molecule_presentations_per_second': 'molecule_presentations',
              'native_atoms_per_second': 'base_atoms',
              'encoder_atoms_per_second': 'encoder_atoms'}
    return {'throughput_scope': 'unprofiled_steps' if any(not row['profiled'] for row in rows) else 'profiled_smoke_only',
            'throughput_step_ordinals': [row['ordinal'] for row in selected],
            'throughput_elapsed_seconds': duration,
            **{key: sum(row[source] for row in selected) / duration for key, source in fields.items()}}
