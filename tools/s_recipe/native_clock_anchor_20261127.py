"""Bounded cross-host freshness without extending a native task's deadline."""
import time


def native_clock_anchor(created_at):
    now=time.time()
    age=now-created_at
    if not -5<=age<=60:
        raise ValueError('Native contract clock age outside [-5,60] seconds: '+str(age))
    return min(created_at,now)
