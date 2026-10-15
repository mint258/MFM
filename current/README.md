# PhyChem-MFM ICLR 2027

Independent shared-backbone multi-supervision refactor of the archived PhyChem-MFM implementation.

The framework exposes two orthogonal experiment axes:

- supervision: `S`, `P`, `D`, `SP`, `SD`, `SPD`;
- task modeling capacity: `shared_light` and `shared_expert`.

Both presets use the same `RealCoordTransformerBackbone`, and both export only shared-backbone `H0` as the canonical downstream representation. Expert Transformers serve prediction objectives only. There is no gate, routing balance loss, branch concatenation, or learned fusion.

See `configs/iclr2027/base.yaml` and `scripts/train.py` after installation.
