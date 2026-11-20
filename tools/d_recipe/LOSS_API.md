# D loss wrapper

`loss.py` is isolated new logic; it changes no P trainer or loss function. The
entry point `compute_d_loss` defaults to `enabled=False`. In that mode it calls
`legacy_loss()` and returns the exact object returned by the original loss. It
does not inspect D inputs, draw random numbers, clip targets, or change reduction.

For D runs only, call with `enabled=True` and three mappings whose keys are
`graph_2d`, `molecule_3d`, and `atom_sasa`. Each value has shape `(molecules,
items)`. Predictions and targets must already be standardized with their frozen
parameters. SASA items are padded atoms in original source atom order; padding
is source-invalid. The caller remains responsible for the taskbook's source
atom-ID alignment acceptance and fixed initialization/sampling.

Supply `DBlockWeights` from the preregistered D-R0 active-field anchor. No
production weights are invented here. Each molecule's observed item losses are
averaged within each block, with an empty block contributing zero. These means
are multiplied by the frozen block totals, summed, then averaged over molecules.
The registered Huber delta must be passed unchanged (default 1). Standardized
targets alone are clipped to ±6 for the loss, without modifying caller storage.

For D-G1 set `include_3d=False`; neither deleted block's weight is redistributed.
For conditional D-K1 only, set `graph_mask_enabled=True` and provide an explicit
dedicated `torch.Generator` of the same device type as the input, separate from
the molecule/conformer sampler. Its state must be saved and restored by the
training checkpoint. The single fixed drop probability is
0.85. No rate-selection API is exposed. `DLossResult.masks` separately records
original source validity, random dropped terms, and effective validity. Invalid
source terms are never recorded as randomly dropped. Empty unmasked blocks
remain zero; 3D masks and losses are unaffected.

`tests/test_d_recipe_loss.py` covers the new logic only, including exact legacy
object/bit identity and unchanged RNG with the option disabled, gradient-level
3D weight invariance to 2D width, target clipping without storage mutation,
source missingness, valid zeroes, empty blocks, no redistribution in D-G1, mask
state replay, and a six-binomial-standard-error absolute and relative bound on
the fixed masking rate. Run this test only on an allocated CPU node. Integration
with a real loader, trainer, checkpoints and overfit acceptance is still needed;
these helper tests do not claim any of that scientific acceptance.
