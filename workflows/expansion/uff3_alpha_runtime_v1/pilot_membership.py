"""Exact existing generation pilot membership, independently checked by QA."""
import random


def validate(db):
    rng=random.Random(20261025);expected=set()
    for stream in ('R','N'):
        for rank in rng.sample(range(1,1250001),5000):
            rows=db.execute('SELECT mid FROM source WHERE stream=? AND stream_rank=?',(stream,rank)).fetchall()
            if len(rows)!=1:raise RuntimeError('PILOT_FROZEN_SOURCE_RANK_MISSING_OR_DUPLICATE')
            expected.add(rows[0][0])
    observed={row[0]for row in db.execute('SELECT s.mid FROM source s JOIN done d USING(ordinal)')}
    if len(expected)!=10000 or observed!=expected:
        raise RuntimeError('PILOT_DONE_MUST_EQUAL_FROZEN_R5000_N5000_MEMBERSHIP_NO_DROP_OR_SUBSTITUTION')
    return 10000