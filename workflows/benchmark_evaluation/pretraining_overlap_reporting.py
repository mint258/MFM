"""Report the registered C1 pretraining-overlap status without examining predictions."""
OVERLAP_FIELDS=frozenset(("pretraining_TEST_overlap_check","pretraining_molecule_inventory_status",
                          "pretraining_overlap_exclusion_applied"))

def annotate_overlap_status(rows):
    """Copy every final seed row unchanged, adding only explicit non-scientific provenance."""
    output=[]
    for row in rows:
        if not isinstance(row,dict) or row.get("learner") not in {"LightGBM","TabPFN"}:
            raise ValueError("Only the registered C1 learners may receive this provenance label")
        if OVERLAP_FIELDS.intersection(row):
            raise ValueError("Do not overwrite or silently replace an existing pretraining-overlap assessment")
        metadata=(dict(pretraining_TEST_overlap_check="未检查",
                       pretraining_molecule_inventory_status="NOT_OBTAINED_IN_THIS_BENCHMARK",
                       pretraining_overlap_exclusion_applied=False)
                  if row["learner"]=="TabPFN" else
                  dict(pretraining_TEST_overlap_check="NOT_APPLICABLE_NO_PRETRAINING",
                       pretraining_molecule_inventory_status="NO_PRETRAINING",
                       pretraining_overlap_exclusion_applied=False))
        output.append(dict(row,**metadata))
    return output
