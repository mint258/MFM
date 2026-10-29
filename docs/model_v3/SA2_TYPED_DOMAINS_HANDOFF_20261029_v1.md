# SA-2 typed-domain handoff — 2026-10-29

Author: SA-2. Worktree: `MFM_model_v3_clean_integration_v1`.
Status: implementation and synthetic test sources prepared; author has not run Python, AST, pytest, Git, Slurm, or scientific computation. Root owns submission and actual validation. No commit or generated QA package was created.

## Implemented

- `phase1/v3_contract.py`: new scalar-regression `ordered_entry` level and graph-regression `symmetric_tensor6` representation (width six, delta one). Existing FieldSpec defaults and serialized fields are unchanged. Typed targets cannot be replaced by a generic FieldTarget. Tensor normalization accepts only center `(0,)` and one positive TRAIN scale; no fit or substitute statistic is implemented.
- `phase1/v3_losses.py`: calls Root's ordinary `tensor6_radial_huber` on raw predictions/labels with one shared scale, original component masks, same-actual-geometry qualification and separate exposure. One eligible tensor is one observation and one field. Ordered entries use an observed-entry Huber mean. Zero eligible fields do not enter the field mean; existing enabled S/D/P group denominators remain. `V3LossResult.audit_counts` has an empty default for legacy callers and exposes source component/entry counts.
- `model/v3_ordered_entries.py`: source-frame v2 uses independent endpoint channel embeddings, ordered endpoint H0, and explicit numeric source coordinates `(pos - frame_origin) @ frame_basis.T`. Numeric origin `[G,3]` and orthogonal basis `[G,3,3]` are independent source metadata; the head rejects missing values and supplies no centroid, zero origin or identity basis default. Onsite, direction and duplicates are retained. Under the passive coordinate re-expression `X'=XR+t`, `O'=OR+t`, `B'=BR`, these features are unchanged. This does not establish an active rotation law for the retained AO-entry list, exchange symmetry, or a complete-AO representation. Ordinals, labels and reasons never enter the head. Its checkpoint feature contract is `model_v3_source_frame_ordered_head_v2`, with explicit passive-only and active-law-unverified declarations plus literal codebook and target/condition/unit/sign/frame/origin/joint-policy bindings.
- `model/v3_heads.py`: preserves SA-4 pooling changes and legacy default extra state. Dedicated ordered/tensor heads require explicit configurations. Active typed heads require independent actual-position `geometry_context`; IDs, source bindings and native memberships are checked. Ordinary pair indices and prediction offsets are rejected for typed domains.
- `model/v3_multiview.py`, `phase1/v3_architecture_views.py`, and `V3PretrainingModel`: optional typed inputs/context follow original clean H0 and coordinates. Legacy calls do not add new kwargs. `phase1/v3_structural.py` propagates typed audit counts through the existing group combination.

## Public configuration and routing

`V3HeadBank(..., domain_head_configs={...})` requires a configuration for every typed registry field:

```python
{
    "ordered_field": {"codebook": {"tokens": ["literal-channel"], "source": codebook_rawref},
                      "frame_binding": source_frame,
                      "channel_dim": 16},  # channel_dim is optional
    "tensor_field": {"origin_policy": "explicit_comoving", "frame_binding": tensor_frame},
}
```

The codebook configuration accepts exactly the JSON `tokens`/`source` record above, and the existing typed `ChannelCodebook` program API remains accepted. Additional codebook keys such as values or entry ordinals are rejected. Typed head extra state contains only plain JSON metadata; codebook tokens are lists. Tuple-token metadata is accepted only when the rest of the same v2 feature/codebook/frame contract matches after JSON normalization. This compatibility does not admit the obsolete v1 absolute-position feature contract: strict restoration rejects that schema. No real v1 ordered-head checkpoint was accepted. No proxy/common validator change was required.

`forward` / `forward_pretrain` accept optional `domain_inputs` and `geometry_context`. The latter has exactly `geometry_ids`, `geometry_bindings`, and `native_atom_counts`, supplied independently from decoded original positions by Root's Data/Prepared integration. Ordered inputs additionally compare their source-geometry bindings and carry independent numeric `frame_origin`/`frame_basis`; the real adapter requires their bound `source_frame_metadata` reference, and target-versus-input numeric frame identity must agree. Transport/audit may retain both frame tensors as `None`, but head execution rejects that audit-only state. These checks and the passive coordinate-re-expression tests do not validate the physical active-rotation law of a retained AO list or grant real-data admission. Tensor origins retain their independent origin provenance; they are never inferred from centroids or label values.

## Prepared validation sources

- `current/tests/model_v3_typed_fixture.py`
- `current/tests/test_model_v3_typed_contract.py`
- `current/tests/test_model_v3_typed_losses.py`
- `current/tests/test_model_v3_ordered_entries.py`
- `current/tests/test_model_v3_typed_heads_integration.py`

Coverage includes legacy serialization/checkpoints and pooling, complete versus partial/mismatched tensors, Frobenius off-diagonal weights and d9 radial Huber, equal group means, source counts, masked NaNs, disconnected empty/disabled heads, detached labels, endpoint/codebook/frame bindings, checkpoint mismatches, both clean-view wrappers, and original H0 routing. The tiny encoder in routing tests tests transport only and is not a scientific/equivariance acceptance model. A further test builds the actual factory 512-dimensional encoder with two molecules (two and three atoms), seals and rereads a JSON configuration through `write_once/read_bound`, verifies its canonical hash, then uses the production safe checkpoint writer/strict loader to restore original H0 and typed predictions. This is explicitly an initial untrained configuration/checkpoint interoperability test, not D3, overfitting, optimizer-resume or scientific acceptance. Root should validate these together with the owned rank2/domain/adapter tests and existing relevant regression tests. Author has not run the new test.

## Scientific admission remains HOLD

This implementation does not publish D1 joint ACK, real D3/D4/D5/D6, a real normalization value, a physical-law decision, or a successful real-data consumer acceptance. D4 must provide the actual target/condition TRAIN Frobenius-series 0.1%/99.9% winsorized `std_ddof0`, with its actual population/key/source bindings. Original 192 coordinate UNKNOWNs and prior equivariance failures remain. No stopped FP32 compensation module was imported, modified, diagnosed, or enabled; no label center, trace projection, imputation, clipping, 1.5 factor, epsilon scale, or extra tensor task weight was added.
