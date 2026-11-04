"""Disjoint exact query work allocation; never a scientific subset replacement."""
import re

HEX = '0123456789abcdef'


def need(value, message):
    if not value:
        raise ValueError(message)


def assignment(plan):
    values = plan['assigned_hash_buckets']
    need(type(values) is list and values and all(type(v) is str and v in HEX and len(v) == 1 for v in values)
         and values == sorted(set(values)), 'Explicit sorted unique lowercase MD5 first-nibble assignment required')
    need(type(plan['partition_id']) is str and re.fullmatch('[A-Za-z0-9_-]+', plan['partition_id']),
         'Explicit source-bound work partition ID required')
    return values


def predicate(values):
    need(values and all(type(v) is str and len(v) == 1 and v in HEX for v in values),
         'Literal exact MD5 nibble membership required')
    return "substr(md5(ecfp4_2048_hex),1,1) IN (" + ','.join("'" + v + "'" for v in values) + ')'


def cover(partitions):
    seen = set()
    for values in partitions:
        need(type(values) is list and values and values == sorted(set(values))
             and all(type(v) is str and len(v) == 1 and v in HEX for v in values), 'Canonical partition declaration required')
        need(not seen.intersection(values), 'Exact NN work partitions overlap')
        seen.update(values)
    need(seen == set(HEX), 'Exact NN partitions must cover every MD5 first nibble')
    return list(HEX)
