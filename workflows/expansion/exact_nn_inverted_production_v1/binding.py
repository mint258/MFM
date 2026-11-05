"""Fresh six-field binding for proven equivalent backend; old binding never rewritten."""
import hashlib
from pathlib import Path
from ..alpha_runtime_v1 import common as Q

FIELDS=('filtered_pool_reference','reference','backend_adoption_reference','assigned_hash_buckets','partition_id','scope_key')
PRESERVED=tuple(k for k in FIELDS if k!='backend_adoption_reference')


def check_transition(previous,current,equivalence):
    Q.need(set(previous)==set(current)==set(FIELDS)and all(previous[k]==current[k]for k in PRESERVED),
           'All five non-backend source/reference/partition/scope fields must remain exactly unchanged')
    Q.need(previous['backend_adoption_reference']==equivalence['previous_backend_adoption_reference']
        and current['backend_adoption_reference']==equivalence['native_equivalence_reference']
        and current['reference']==equivalence['reference_manifest_reference']
        and current['filtered_pool_reference']==equivalence['filtered_pool_reference'],
        'Native-equivalence cache reuse is scoped to old206, same196 and same209 only')


def publish(path,value):
    path=Path(path)
    if path.exists():
        Q.need(Q.load(path)==value,'Immutable derived backend metadata collision')
        return Q.reference(path)
    return Q.write(path,value)


def establish(root,current,equivalence):
    """Caller already owns actual parent.lock and proved prior writers terminal."""
    root=Path(root);original=root/'source_binding.json'
    Q.need(set(current)==set(FIELDS),'Exactly the aggregate six-field binding')
    if not original.exists():
        Q.need(all(Q.frame(p)[2]==0 for p in root.glob('closed_files*.jsonl'))and not(root/'scores').exists(),
               'No unbound old cache may be seeded into a fresh backend stage')
        return publish(original,current),None
    previous=Q.load(original);original_ref=Q.reference(original)
    if previous==current:return original_ref,None
    check_transition(previous,current,equivalence)
    token=hashlib.sha256(Q.canonical([original_ref,current])).hexdigest()[:24]
    derived=publish(root/('source_binding_inverted_'+token+'.json'),current)
    lineage=publish(root/('equivalent_backend_continuation_'+token+'.json'),dict(
        original_source_binding_reference=original_ref,derived_source_binding_reference=derived,
        native_equivalence_reference=equivalence['native_equivalence_reference'],
        unchanged_nonbackend_binding={k:current[k]for k in PRESERVED},
        previous_backend_adoption_reference=previous['backend_adoption_reference'],
        original_binding_rewritten=False,closed_score_files_or_journals_rewritten=False))
    Q.need(Q.reference(original)==original_ref,'Original binding changed during derived metadata publication')
    return derived,lineage