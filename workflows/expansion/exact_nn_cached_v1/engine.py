"""Exact popcount-bounded RDKit nearest neighbors, all reference ordinals kept.

No approximate index or reference sample is used. Bounds are compared as exact
integers against the winning intersection/union, never a rounded float bound.
RDKit's original double is returned unchanged, with earliest ordinal ties.
"""
from __future__ import annotations
from array import array
from collections import OrderedDict
from fractions import Fraction
import os
from pathlib import Path
import resource
import stat
import struct
import time

RECIPE='ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5'
WIDTH=256
ALGORITHM='ALL_REFERENCE_CACHED_POPCOUNT_EXACT_INTEGER_BOUNDS_V1'


def modules():
    from rdkit import DataStructs,rdBase
    if rdBase.rdkitVersion!='2025.09.5':
        raise RuntimeError('EXACT_RDKit2025_09_5_REQUIRED')
    return DataStructs


def current_rss():
    path=Path('/proc/self/statm')
    if path.exists():return int(path.read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024


def enforce_rss(cap):
    value=current_rss()
    if type(cap)is not int or cap<=0:raise ValueError('DECLARED_POSITIVE_WORKER_RSS_CAP_REQUIRED')
    if value>cap:raise RuntimeError('ACTUAL_WORKER_RSS_EXCEEDS_DECLARED_CACHE_BUDGET')
    return value


def upper_bound(qbits,rbits):
    """RDKit2025.09.5 returns0 for zero/zero; otherwise min/max is safe."""
    if not (0<=qbits<=2048 and 0<=rbits<=2048):raise ValueError('INVALID_2048BIT_POPCOUNT')
    largest=max(qbits,rbits)
    return (min(qbits,rbits),largest) if largest else (0,1)


def strict_below(upper_num,upper_den,best_num,best_den):
    return upper_num*best_den < best_num*upper_den


class CachedReference:
    def __init__(self,raw_fingerprints,*,worker_rss_cap_bytes):
        self.ds=modules();self.cap=worker_rss_cap_bytes
        self.groups={};self.n=0;self.orders=OrderedDict();self.decode_calls=0
        start=time.monotonic()
        enforce_rss(self.cap)
        for ordinal,raw in enumerate(raw_fingerprints):
            if not isinstance(raw,bytes) or len(raw)!=WIDTH:raise ValueError('EXACT_2048BIT_RAW_REFERENCE_REQUIRED')
            vector=self.ds.CreateFromBinaryText(raw)
            if vector.GetNumBits()!=2048:raise ValueError('REFERENCE_WIDTH_CHANGED')
            count=int(vector.GetNumOnBits())
            if count not in self.groups:self.groups[count]=(array('Q'),[])
            ordinals,vectors=self.groups[count]
            ordinals.append(ordinal);vectors.append(vector)
            self.n+=1;self.decode_calls+=1
            if self.n%4096==0:enforce_rss(self.cap)
        if self.n<1:raise ValueError('EMPTY_REFERENCE_FORBIDDEN')
        self.load_rss_bytes=enforce_rss(self.cap)
        self.bulk_buffer_allowance_bytes=max(len(value[1]) for value in self.groups.values())*80+(16<<20)
        if self.load_rss_bytes+self.bulk_buffer_allowance_bytes>self.cap:
            raise RuntimeError('DECLARED_RSS_BUDGET_MUST_COVER_DECODED_REFERENCE_AND_BULK_RESULT_BUFFER')
        self.last_rss_poll=time.monotonic()
        self.load_wall_seconds=time.monotonic()-start

    def order(self,qbits):
        if qbits not in self.orders:
            values=[(*upper_bound(qbits,pop),pop) for pop in self.groups]
            values.sort(key=lambda v:(-Fraction(v[0],v[1]),v[2]))
            self.orders[qbits]=tuple(values)
            if len(self.orders)>64:self.orders.popitem(last=False)
        else:self.orders.move_to_end(qbits)
        return self.orders[qbits]

    def nearest(self,raw):
        if not isinstance(raw,bytes) or len(raw)!=WIDTH:raise ValueError('EXACT_2048BIT_RAW_QUERY_REQUIRED')
        query=self.ds.CreateFromBinaryText(raw)
        qbits=int(query.GetNumOnBits());best=-1.;ordinal=-1
        best_num,best_den=0,1;evaluated=pruned=0;searched_groups=[]
        for upper_num,upper_den,pop in self.order(qbits):
            ordinals,vectors=self.groups[pop]
            if ordinal>=0 and strict_below(upper_num,upper_den,best_num,best_den):
                pruned+=len(vectors)
                continue
            scores=self.ds.BulkTanimotoSimilarity(query,vectors)
            evaluated+=len(vectors);searched_groups.append(pop)
            score=max(scores);local=scores.index(score);index=int(ordinals[local])
            if score>best or (score==best and (ordinal<0 or index<ordinal)):
                common=int((query & vectors[local]).GetNumOnBits())
                union=qbits+pop-common
                numerator,denominator=(common,union) if union else (0,1)
                # Official BitOps.cpp casts these small integers to double and
                # divides; compare bits rather than introducing a new score.
                if struct.pack('<d',score)!=struct.pack('<d',numerator/denominator):
                    raise RuntimeError('RDKit_TANIMOTO_DOUBLE_DIFFERS_FROM_EXACT_SMALL_INTEGER_RATIO')
                best,ordinal,best_num,best_den=float(score),index,numerator,denominator
        if ordinal<0 or evaluated+pruned!=self.n:raise RuntimeError('INCOMPLETE_REFERENCE_GROUP_ACCOUNTING')
        if time.monotonic()-self.last_rss_poll>=5:
            enforce_rss(self.cap);self.last_rss_poll=time.monotonic()
        return {'score':best,'reference_ordinal':ordinal,'score_numerator':best_num,
            'score_denominator':best_den,'evaluated_references':evaluated,
            'strictly_bound_pruned_references':pruned,'reference_molecules':self.n,
            'searched_popcount_groups':searched_groups}


def file_frame(path):
    value=Path(path).lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_uid!=os.getuid():
        raise ValueError('OWN_REGULAR_REFERENCE_REQUIRED')
    return [value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_uid]


def load_reference(path,expected_frame,n,worker_rss_cap_bytes):
    path=Path(path)
    if file_frame(path)!=expected_frame or expected_frame[2]!=n*WIDTH:
        raise ValueError('REFERENCE_FILE_IDENTITY_OR_CARDINALITY_CHANGED')
    with path.open('rb',buffering=8<<20) as stream:
        observed=os.fstat(stream.fileno())
        if [observed.st_dev,observed.st_ino,observed.st_size,observed.st_mtime_ns,observed.st_uid]!=expected_frame:
            raise ValueError('SAME_REFERENCE_FD_REQUIRED')
        result=CachedReference(iter(lambda:stream.read(WIDTH),b''),worker_rss_cap_bytes=worker_rss_cap_bytes)
        after=os.fstat(stream.fileno())
        if [after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_uid]!=expected_frame:
            raise ValueError('REFERENCE_CHANGED_DURING_DECODE')
    if file_frame(path)!=expected_frame or result.n!=n:raise ValueError('REFERENCE_CHANGED_OR_SHORT_DURING_DECODE')
    return result
