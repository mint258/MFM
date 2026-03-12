# descriptor_integration_2ep

## Run setup

- Environment: `C:\Users\mint\.conda\envs\chemprop\python.exe`
- Device: `cpu`
- Dataset: `test_data/principal_valid_test.lmdb`
- Split:
  - train: indices `875..8754` (`7880` samples)
  - val: indices `0..874` (`875` samples)
- Epochs: `2`
- Batch size: `16`
- Model:
  - hidden channels: `64`
  - backbone layers: `2`
  - experts per branch: `1 / 1 / 1 / 1`
  - expert real layers: `1`
- Loss weights:
  - `lambda_e=1.0`
  - `lambda_e_desc=0.5`
  - `lambda_q=1.0`
  - `lambda_q_desc=0.5`
  - `lambda_z=1.0`
  - `lambda_z_desc=0.5`
  - `lambda_dist=1.0`

## Final metrics

Epoch 1:

- Train: `E=1.101`, `E_desc=2.838`, `Q=1.061`, `Q_desc=0.168`, `Z=1.275`, `Z_desc=0.758`, `Geom=3.599`
- Val: `E=0.852`, `E_desc=2.196`, `Q=0.208`, `Q_desc=0.034`, `Z=0.797`, `Z_desc=0.259`, `Geom=3.124`

Epoch 2:

- Train: `E=1.089`, `E_desc=2.220`, `Q=0.231`, `Q_desc=0.038`, `Z=0.805`, `Z_desc=0.257`, `Geom=2.939`
- Val: `E=0.846`, `E_desc=2.067`, `Q=0.195`, `Q_desc=0.030`, `Z=0.790`, `Z_desc=0.212`, `Geom=2.950`

Best validation selection loss:

- `5.93622` at epoch `2`

## Artifacts

- Best checkpoint: `test_ckpt/descriptor_integration_2ep.pt`
- W&B offline run: `wandb/wandb/offline-run-20260313_001953-i5o2f4si`
