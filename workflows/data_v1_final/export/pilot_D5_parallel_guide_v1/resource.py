"""Conservative D5 resource accounting with no active domain allocation credit.

The mutable domain.sqlite remains excluded from immutable closed-output credit.
Its allocated blocks are never used to lower future reservations or subjected
to a monotonicity check. All original full-cap, quota, RSS, wall and DATA
identity checks remain in the inherited budget.
"""
import types
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import io as I

WORKER_RSS_CAP_BYTES = 3 << 30
OLD_WORKER_RSS_CAP_BYTES = 1500000000
_PRIVATE_WORKER_CHECK = None


class ObjectProxy:
    """Forward every original object except explicitly named private IO bindings."""

    def __init__(self, original, **overrides):
        self.original = original
        self.overrides = overrides

    def __getattr__(self, name):
        if name in self.overrides:
            return self.overrides[name]
        return getattr(self.original, name)


class WorkerRSSProxy(ObjectProxy):
    def soft_worker_rss(self, cap):
        # Only the deployed 1.5-GB worker soft bound changes. Other caps,
        # measurements, STOP propagation and all mathematical objects remain.
        return self.original.soft_worker_rss(
            WORKER_RSS_CAP_BYTES if cap == OLD_WORKER_RSS_CAP_BYTES else cap)


def clone(function, **bindings):
    namespace = dict(function.__globals__)
    namespace.update(bindings)
    private = types.FunctionType(function.__code__, namespace, function.__name__,
                                 function.__defaults__, function.__closure__)
    private.__kwdefaults__ = function.__kwdefaults__
    return private


def worker_check(control, additional=0):
    """Original outer and nested worker checks, with only the RSS IO cap changed."""
    global _PRIVATE_WORKER_CHECK
    if _PRIVATE_WORKER_CHECK is None:
        outer = I.F.worker_check
        nested_module = outer.__globals__['R']
        nested = nested_module.worker_check
        private_nested = clone(nested, R=WorkerRSSProxy(nested.__globals__['R']))
        _PRIVATE_WORKER_CHECK = clone(outer,
            OBS=WorkerRSSProxy(outer.__globals__['OBS']),
            R=ObjectProxy(nested_module, worker_check=private_nested))
    return _PRIVATE_WORKER_CHECK(control, additional)


def project(work, *, reader_records=None):
    """Original X.one bytecode with a private RSS-only IO proxy.

    A D5 caller may retain its existing diagnostic records adapter. A future
    D3 parent can submit one(work) with its original X.initialize context.
    """
    from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import source as X
    bindings = dict(I=ObjectProxy(I, F=ObjectProxy(I.F, worker_check=worker_check)), CTX=X.CTX)
    if reader_records is not None:
        bindings['R'] = types.SimpleNamespace(records=reader_records)
    return clone(X.one, **bindings)(work)


def one(work):
    """Pickleable future-D3 entry: original records, private 3-GiB RSS IO only."""
    return project(work)


class CreditlessDomainMath(I.ActiveDomainMath):
    """Keep the complete own future cap even when the mutable DB already exists."""

    def remaining_future(self, total, cap, closed):
        remaining = self.original.remaining_future(total, cap, closed)
        self.last_report = dict(
            schema='CURRENT_PARENT_ACTIVE_DOMAIN_ALLOCATED_RESOURCE_CREDIT_V1',
            path=str(self.path), domain_exists=self.path.exists(), credit_disabled=True,
            earlier_quota_covered_domain_allocated_bytes=0,
            total_future_reserved_bytes=total, original_full_parent_cap_bytes=cap,
            separate_closed_output_allocated_bytes=closed,
            remaining_future_reserved_bytes=remaining,
            database_excluded_from_second_immutable_credit=True,
            mutable_domain_allocated_blocks_observed=False,
            mutable_domain_monotonicity_admission_applied=False,
            free_bytes_rewritten=False, SQL_or_database_body_read=False,
            scientific_adoption=False, quota_reserve_bytes=self.budget.account_floor_bytes)
        return remaining

    def report(self):
        value = dict(self.last_report) if self.last_report is not None else dict(
            schema='CURRENT_PARENT_ACTIVE_DOMAIN_ALLOCATED_RESOURCE_CREDIT_V1',
            path=str(self.path), earlier_quota_covered_domain_allocated_bytes=0,
            database_excluded_from_second_immutable_credit=True,
            mutable_domain_allocated_blocks_observed=False,
            mutable_domain_monotonicity_admission_applied=False,
            SQL_or_database_body_read=False, scientific_adoption=False,
            quota_reserve_bytes=self.budget.account_floor_bytes)
        value.update(domain_exists=self.path.exists(), credit_disabled=True)
        return value


class Budget(I.Budget):
    """Original initialization bytecode with only the own-credit factory changed."""

    def __init__(self, plan, proof, root):
        original = I.Budget.__init__
        namespace = dict(original.__globals__)
        namespace['ActiveDomainMath'] = CreditlessDomainMath
        initialize = types.FunctionType(original.__code__, namespace, original.__name__,
                                        original.__defaults__, original.__closure__)
        initialize.__kwdefaults__ = original.__kwdefaults__
        initialize(self, plan, proof, root)
        # The cloned initializer's global write is private. Preserve the original
        # I.save/report complete-census binding for the rest of this D5 process.
        I.ACTIVE_CENSUS = self.census_context
