# R4 resource-only packed day protocol v2

One real Main CPU parent, 86400s including 900s natural drain, no memory,
exclusive, GPU, child sbatch or artificial child C0. Root selects integer
16..96 allocated CPUs and one actually mapped compute-0-14 or compute-0-18.
The producer module/KEY remain sprime_packed_day_v1. New request/proof/
submission schemas and control namespace are V2; historical V1 remains frozen.

Provider Client, parser, freshness, marker, publisher and read functions are
direct cpu_analysis_day_v1 objects. No new publisher implementation is present.
Root starts a distinct finite90000s instance for this parent; release requires
at least86700s remaining. Old13 publishers/identities remain historical/live
as applicable and cannot be substituted for this node's review.

Root input schema remains ROOT_REQUESTED_SPRIME_PACKED_DAY_V1. Add actual node,
cpus, producer_plan_reference and all real resource refs. Carveout retains the
existing ROOT_PACKED_DAY_EXISTING182_RESOURCE_CARVEOUT_V1 schema and adds exact
node. Future writer cap is included once; all original account reserve gates
remain. Draft/finalize/submit/observe are the original mechanism in namespace:

    PY -B -m workflows.data_v1_final.execution.cpu_packed_day_v2.materialize draft --request ROOT_REQUEST
    PY -B -m workflows.data_v1_final.execution.cpu_packed_day_v2.materialize finalize --draft DRAFT --root-review ROOT_REVIEW
    PY -B -m workflows.data_v1_final.execution.cpu_packed_day_v2.submit --request REQUEST
    PY -B -m workflows.data_v1_final.execution.cpu_packed_day_v2.observe --submission ACTUAL_SUBMISSION

quota_origin.json embeds the exact pre-revision Source bytes and explicit
finite edit pairs for all38 resource/producer/postprocess leaves (excluding
the witness itself). The same Parent's original3 resource methods perform
complete byte/AST inversion and verify frozen shared provider Source; the
producer retains6 methods (9 total before DATA), postprocess retains28.
Authoring ran no project Python, AST, tests, scientific DATA or Slurm.
