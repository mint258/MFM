# Future fill-only loader without unused HOF/prior materialization

The original slow fill worker uses every original PM7 pointer: it reads native energies, selects minimum (energy,RID), and verifies all native graphs/atom order. It never reads HOF value_json/duplicate or prior_packet. The new independent `window2_fill_loader_v1` therefore changes only two input operations: formal uses the same SELECT f.* JOIN batch and MID/RID ordering without LEFT JOIN hof; prior is not read, and its unused task key is None. The original full UFF SELECT u.* ordering and all conformer indices/F64 rows remain intact.

A private function namespace injects this loader into the existing passed fast part_values, then injects that function into the same existing producer loop. No active module/global function is patched. Active fast.run, fill.py and d7.py are unchanged. Fast eligibility/stubs, original safe_fill, all Native energy/graph work, max-ID handling, seeds, candidate/RMSD/N logic, state order, closed parts/checkpoints and new-geometry writing remain the existing implementation.

Root alone switches the future entry point at a completed-part boundary. Nothing here sends signals, submits Slurm or reads actual tables for QA. The new actual parent runs only this one new in-memory fixture test; previously passed tests are not repeated:

    python -B -m unittest workflows.data_v1_final.conformers.window2_fill_loader_v1.test_v1
    python -B -m workflows.data_v1_final.conformers.window2_fill_loader_v1.run --plan ORIGINAL_EXISTING_FILL_PLAN

The test compares every formal field except the two unused HOF columns and every UFF field/value/order against original d7.tasks; verifies input meta order, all pointer fields and maximum-index candidates remain available; rejects HOF/prior queries through a guard; and exercises the private runtime injection without calling Native. It reads no real scientific data and performs no benchmark.