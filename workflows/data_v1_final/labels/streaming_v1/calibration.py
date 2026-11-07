"""Exact bounded-rank radix calibration and mergeable small TSQR states.

Median/MAD refinement rereads only original sources; it never keeps all normal
numeric leaves. Full precision may require several source passes. That cost is
explicit and must be measured before Root approves a full phase.
"""
from __future__ import annotations

import collections
from fractions import Fraction
import math
import struct


def float_key(value):
    if math.isnan(value):
        raise ValueError("NAN_NOT_A_CALIBRATION_OBSERVATION")
    value=0.0 if value==0 else value
    u=struct.unpack("<Q",struct.pack("<d",value))[0]
    return u^(0xFFFFFFFFFFFFFFFF if u>>63 else 0x8000000000000000)


def key_float(key):
    key=int(key)
    u=key^(0x8000000000000000 if key>>63 else 0xFFFFFFFFFFFFFFFF)
    return struct.unpack("<d",struct.pack("<Q",u))[0]


def exact_mean_pair(a,b):
    if a==b:return a
    if not (math.isfinite(a) and math.isfinite(b)):
        return (a+b)/2
    return float((Fraction.from_float(a)+Fraction.from_float(b))/2)


def initial_queries(fields,purpose="median",centers=None,probability="0.5"):
    probability=Fraction(str(probability))
    if not 0<=probability<=1:raise ValueError("QUANTILE_OUTSIDE_ZERO_ONE")
    rows=[]
    for field in fields:
        fid=field["field_id"]
        if purpose=="MAD" and (centers is None or fid not in centers):
            continue
        rows.append({"field_id":fid,"transform":"abs_center" if purpose=="MAD" else "identity",
            "center":centers[fid] if purpose=="MAD" else None,"n_total":None,"resolved_keys":{},
            "nodes":[{"node_id":str(fid)+"_root","prefix_bits":0,"prefix":"0","targets":None,"expected_count":None}]})
    return {"schema":"EXACT_F64_RADIX_QUERIES_V1","purpose":purpose,"probability":str(probability),"round":0,"fields":rows,
        "statistics_zero_policy":"-0 and +0 pooled as numeric zero; source labels unchanged"}


class RadixCounts:
    def __init__(self,request):
        self.request=request
        self.by_id={row["field_id"]:row for row in request["fields"]}
        self.counts=collections.Counter()

    def add(self,fid,values):
        import numpy as np
        field=self.by_id.get(fid)
        if field is None or not len(values):return
        a=np.asarray(values,dtype=np.float64)
        if not np.isfinite(a).all():
            raise ValueError("NONFINITE_SOURCE_LEAF_REACHED_TRAIN_CALIBRATION")
        if field["transform"]=="abs_center":
            with np.errstate(over="ignore"):
                a=np.abs(a-float(field["center"]))
        a=np.where(a==0,0.0,a)
        raw=a.view(np.uint64)
        keys=raw^np.where(raw>>63,np.uint64(0xFFFFFFFFFFFFFFFF),np.uint64(0x8000000000000000))
        for node in field["nodes"]:
            old=int(node["prefix_bits"]);new=min(64,16 if old==0 else old+8)
            selected=keys if old==0 else keys[(keys>>np.uint64(64-old))==np.uint64(int(node["prefix"]))]
            prefixes=selected if new==64 else selected>>np.uint64(64-new)
            unique,count=np.unique(prefixes,return_counts=True)
            for prefix,n in zip(unique,count):
                self.counts[(fid,node["node_id"],new,int(prefix))]+=int(n)

    def rows(self):
        return [{"field_id":fid,"node_id":node,"prefix_bits":bits,"prefix":prefix,"n":n}
            for (fid,node,bits,prefix),n in sorted(self.counts.items())]


def advance(request,rows):
    grouped=collections.defaultdict(collections.Counter)
    for row in rows:
        grouped[(int(row["field_id"]),row["node_id"],int(row["prefix_bits"]))][int(row["prefix"])]+=int(row["n"])
    next_fields=[];finished=[]
    for field in request["fields"]:
        updated={**field,"resolved_keys":dict(field["resolved_keys"]),"nodes":[]}
        n_total=field["n_total"]
        for node in field["nodes"]:
            old=int(node["prefix_bits"]);new=min(64,16 if old==0 else old+8)
            counts=grouped[(field["field_id"],node["node_id"],new)]
            n=sum(counts.values())
            if node["expected_count"] is not None and n!=node["expected_count"]:
                raise ValueError("RADIX_PREFIX_MASS_CHANGED_BETWEEN_PASSES")
            if old==0:
                n_total=n
                if n==0:
                    continue
                position=Fraction(request.get("probability","0.5"))*(n-1)
                lower=position.numerator//position.denominator
                upper=lower+int(position.denominator!=1)
                weight=position-lower
                updated["upper_weight"]=[weight.numerator,weight.denominator]
                targets=[{"name":"lower","rank":lower},{"name":"upper","rank":upper}]
            else:
                targets=node["targets"]
            branches=collections.defaultdict(list)
            for target in targets:
                rank=target["rank"];prior=0;found=False
                for prefix,count in sorted(counts.items()):
                    if prior<=rank<prior+count:
                        if new==64:
                            updated["resolved_keys"][target["name"]]=str(prefix)
                        else:
                            branches[prefix].append({"name":target["name"],"rank":rank-prior})
                        found=True;break
                    prior+=count
                if not found:
                    raise ValueError("RADIX_ORDER_STATISTIC_OUTSIDE_OBSERVED_MASS")
            for prefix,targets in sorted(branches.items()):
                updated["nodes"].append({"node_id":str(field["field_id"])+"_"+str(new)+"_"+str(prefix),
                    "prefix_bits":new,"prefix":str(prefix),"targets":targets,"expected_count":counts[prefix]})
        updated["n_total"]=n_total
        if updated["nodes"]:
            next_fields.append(updated)
        else:
            keys=updated["resolved_keys"]
            value=None
            if n_total:
                lower,upper=key_float(keys["lower"]),key_float(keys["upper"])
                weight=Fraction(*updated["upper_weight"])
                if math.isfinite(lower) and math.isfinite(upper):
                    value=float((1-weight)*Fraction.from_float(lower)+weight*Fraction.from_float(upper))
                else:value=lower if weight==0 else upper if weight==1 else exact_mean_pair(lower,upper)
            finished.append({"field_id":field["field_id"],"n":n_total,"value":value if value is not None and math.isfinite(value) else None,
                "status":"EXACT" if value is not None and math.isfinite(value) else "UNDEFINED_NO_FINITE_SCALE",
                "resolved_keys":keys})
    return {**request,"round":request["round"]+1,"fields":next_fields},finished


def train_values(role,values,masks):
    if role not in {"TRAIN","VAL","FULL","EMBARGO"}:raise ValueError("UNKNOWN_CALIBRATION_ROLE")
    if len(values)!=len(masks):raise ValueError("TRAIN_VALUE_MASK_LENGTH_DIFFERS")
    if role!="TRAIN":return []
    out=[float(v) for v,keep in zip(values,masks) if keep]
    if not all(math.isfinite(v) for v in out):raise ValueError("NONFINITE_UNMASKED_TRAIN_VALUE")
    return out


class WinsorMoments:
    """Mergeable Chan moments; clipping is solely for statistics, never labels."""
    def __init__(self,lower,upper):
        import numpy as np
        if not math.isfinite(lower) or not math.isfinite(upper) or lower>upper:
            raise ValueError("INVALID_TRAIN_WINSOR_QUANTILES")
        self.lower=lower;self.upper=upper;self.n=0;self.mean=np.longdouble(0);self.M2=np.longdouble(0)

    def add(self,values):
        import numpy as np
        a=np.clip(np.asarray(values,dtype=np.longdouble),self.lower,self.upper)
        if not len(a):return
        if not np.isfinite(a).all():raise ValueError("NONFINITE_VALUE_IN_WINSOR_MOMENTS")
        n=len(a);mean=np.mean(a,dtype=np.longdouble);M2=np.sum((a-mean)**2,dtype=np.longdouble)
        total=self.n+n;delta=mean-self.mean
        self.M2+=M2+delta*delta*self.n*n/total;self.mean+=delta*n/total;self.n=total

    def result(self):
        import numpy as np
        return {"n":self.n,"mean":float(self.mean) if self.n else None,
            "std_ddof0":float(np.sqrt(self.M2/self.n)) if self.n else None,
            "winsor_lower":self.lower,"winsor_upper":self.upper,"labels_modified":False}


class TSQR:
    def __init__(self,basis,chunk=256):
        import numpy as np
        self.basis=list(basis);self.chunk=chunk;self.width=len(basis)+1
        self.R=np.empty((0,self.width));self.z=np.empty(0)
        self.x=[];self.y=[];self.n=0

    def add(self,numbers,value):
        import numpy as np
        count=collections.Counter(numbers)
        if set(count)-set(self.basis):
            raise ValueError("TRAIN_ATOMIC_NUMBER_OUTSIDE_PINNED_REFERENCE_BASIS")
        self.x.append([float(count[z]) for z in self.basis]+[1.0]);self.y.append(float(value));self.n+=1
        if len(self.y)>=self.chunk:self.flush()

    def flush(self):
        import numpy as np
        if not self.y:return
        a=np.concatenate((self.R,np.asarray(self.x,dtype=np.float64)))
        b=np.concatenate((self.z,np.asarray(self.y,dtype=np.float64)))
        Q,self.R=np.linalg.qr(a,mode="reduced");self.z=Q.T@b
        self.x.clear();self.y.clear()

    def state(self):
        self.flush()
        return {"basis":self.basis,"n":self.n,"R":self.R.tolist(),"z":self.z.tolist(),"chunk":self.chunk}


def merge_qr(states):
    import numpy as np
    active=[s for s in states if s["n"]]
    if not active:return {"status":"NO_VALID_TRAIN_ENERGY"}
    basis=active[0]["basis"];R=np.empty((0,len(basis)+1));z=np.empty(0)
    for s in active:
        if s["basis"]!=basis:raise ValueError("REFERENCE_BASIS_DIFFERS_ACROSS_SOURCE_GROUPS")
        a=np.concatenate((R,np.asarray(s["R"],dtype=np.float64)))
        b=np.concatenate((z,np.asarray(s["z"],dtype=np.float64)))
        Q,R=np.linalg.qr(a,mode="reduced");z=Q.T@b
    coef,_,rank,singular=np.linalg.lstsq(R,z,rcond=1e-12)
    return {"status":"TRAIN_ANOMALY_SIZE_REFERENCE_NOT_FINAL_NORMALIZATION","basis":basis,
        "coefficients":coef[:-1].tolist(),"intercept":float(coef[-1]),"rank":int(rank),
        "singular_values":singular.tolist(),"rcond":1e-12,"n":sum(s["n"] for s in active),
        "algorithm":"per-source-group TSQR; deterministic group-order TSQR reduction; TRAIN only"}


def weighted_spearman(rows):
    """Small semantic oracle; production uses the equivalent external SQL ranks."""
    import numpy as np
    joint=collections.Counter()
    for value,heavy,n in rows:joint[(float(value),int(heavy))]+=int(n)
    yc=collections.Counter();xc=collections.Counter()
    for (y,x),n in joint.items():yc[y]+=n;xc[x]+=n
    total=sum(joint.values())
    if total<2 or len(yc)<2 or len(xc)<2:return {"n":total,"rho":None}
    def ranks(counts):
        out={};prior=0
        for value,n in sorted(counts.items()):out[value]=prior+(n+1)/2;prior+=n
        return out
    yr,xr=ranks(yc),ranks(xc);center=np.longdouble(total+1)/2
    xx=yy=xy=np.longdouble(0)
    for (y,x),n in joint.items():
        a=np.longdouble(xr[x])-center;b=np.longdouble(yr[y])-center
        xx+=n*a*a;yy+=n*b*b;xy+=n*a*b
    return {"n":total,"rho":float(xy/np.sqrt(xx*yy))}
