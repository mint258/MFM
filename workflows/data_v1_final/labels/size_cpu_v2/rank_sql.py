"""Exact average-tie Spearman over bounded weighted scalar histograms."""
from __future__ import annotations

import math
from size_shared import path_list,sqlstr,checkpoint,checkpoint_iter


def rho(db,paths,target,variant):
    checkpoint()
    import numpy as np
    db.execute("CREATE OR REPLACE TEMP TABLE size_joint AS SELECT value,heavy_atoms,sum(n)::UBIGINT n FROM read_parquet("+
        path_list(paths)+") WHERE target_id="+sqlstr(target)+" AND variant="+sqlstr(variant)+
        " GROUP BY value,heavy_atoms")
    total,ny,nx=db.execute("SELECT coalesce(sum(n),0),count(DISTINCT value),count(DISTINCT heavy_atoms) FROM size_joint").fetchone()
    total=int(total)
    result={"pair_n":total,"unique_values":ny,"unique_heavy_counts":nx,"rho":None,
            "tie_policy":"exact average ranks; numeric signed zero pooled; no winsorization"}
    if total<2:result["status"]="FEWER_THAN_TWO_PAIRS";return result
    if ny<2:result["status"]="CONSTANT_AGGREGATE";return result
    if nx<2:result["status"]="CONSTANT_HEAVY_COUNT";return result
    db.execute("""CREATE OR REPLACE TEMP TABLE size_yrank AS SELECT value,
        sum(n) OVER(ORDER BY value ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)-(n-1)/2.0 AS rank
        FROM (SELECT value,sum(n)::UBIGINT n FROM size_joint GROUP BY value)""")
    db.execute("""CREATE OR REPLACE TEMP TABLE size_xrank AS SELECT heavy_atoms,
        sum(n) OVER(ORDER BY heavy_atoms ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)-(n-1)/2.0 AS rank
        FROM (SELECT heavy_atoms,sum(n)::UBIGINT n FROM size_joint GROUP BY heavy_atoms)""")
    checkpoint()
    batches=db.execute("SELECT j.n,x.rank,y.rank FROM size_joint j JOIN size_xrank x USING(heavy_atoms) JOIN size_yrank y USING(value) ORDER BY j.value,j.heavy_atoms").fetch_record_batch(4096)
    center=np.longdouble(total+1)/2;xx=yy=xy=np.longdouble(0)
    for batch in checkpoint_iter(batches):
        a=batch.column(1).to_numpy(zero_copy_only=False).astype(np.longdouble)-center
        b=batch.column(2).to_numpy(zero_copy_only=False).astype(np.longdouble)-center
        n=batch.column(0).to_numpy(zero_copy_only=False).astype(np.longdouble)
        xx+=np.sum(n*a*a,dtype=np.longdouble);yy+=np.sum(n*b*b,dtype=np.longdouble);xy+=np.sum(n*a*b,dtype=np.longdouble)
    value=float(xy/np.sqrt(xx*yy))
    if not math.isfinite(value) or abs(value)>1+1e-12:raise ValueError("SIZE_SPEARMAN_NUMERIC_FAILURE")
    result.update(rho=max(-1.,min(1.,value)),status="DEFINED",rounding_clip_tolerance=1e-12)
    return result
