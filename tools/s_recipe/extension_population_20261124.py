"""Opt-in views of the already delivered S population; no new selection RNG.

Original rows retain published fixed_random order after D5 exclusion. The
original geometry sampler and all three-view construction remain unchanged.
"""


def conformer_rows(rows, cap=None):
    if cap is None:
        return rows
    if type(cap) is not int or cap not in (1, 2, 5, 10):
        raise ValueError('Registered conformer cap is1,2,5,10 or disabled')
    result = []
    for row in rows:
        if not row['PM7'] or len(set(row['PM7'])) != len(row['PM7']):
            raise ValueError('Original allowed PM7 list must be nonempty and unique')
        result.append(dict(row, PM7=row['PM7'][:cap]))
    return result


def intersect_saved_mids(rows, saved_mids):
    selected = set(saved_mids)
    if len(selected) != len(saved_mids):
        raise ValueError('Actual P selected MID manifest must be unique')
    return [row for row in rows if row['molecule_id'] in selected]


def population_summary(rows):
    if not rows:
        raise ValueError('No eligible molecules')
    return dict(molecules=len(rows),
                mean_allowed_PM7=sum(len(row['PM7']) for row in rows)/len(rows),
                mean_allowed_UFF=sum(len(row['UFF']) for row in rows)/len(rows))
