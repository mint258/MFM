# MFM ADMET Finetune Pipeline

This directory provides train/predict/ensemble scripts that follow the same fold protocol used by the Chemprop baselines.

## Scripts

- `train.py`: unified training entry for ST/MT.
- `train_ST_MFM.py`: ST wrapper (`--mode st`).
- `train_MT_MFM.py`: MT wrapper (`--mode mt`).
- `predict_CV.py`: evaluate all folds and write `cv_preds.csv`.
- `ensemble.py`: average fold predictions on blinded test data and write `test_ensemble_preds.csv`.

## Benchmark-aligned defaults (important)

- Use smaller batch like Chemprop baseline (`--batch_size 16`).
- Use multiple conformers (`--num_conformers >= 4`; default is 8).
- Use the pretrained MoE experts for embeddings via `--embedding_mode moe_concat`.
- Prefer warmup + cosine schedule (`--init_lr/--max_lr/--final_lr/--warmup_epochs`) for long runs.

## Example: Multi-task

```powershell
py MFM/admet/train_MT_MFM.py `
  --pretrained_ckpt path/to/ckpt_multitask.pt `
  --output_dir mfm_results/MT_MFM_moe `
  --data_dir data `
  --folds 1-10 `
  --num_conformers 8 `
  --embedding_mode moe_concat `
  --epochs 400 `
  --patience 40 `
  --batch_size 16 `
  --init_lr 1e-5 `
  --max_lr 5e-4 `
  --final_lr 2e-5 `
  --warmup_epochs 10 `
  --cache_dir mfm_results/cache_mt
```

```powershell
py MFM/admet/predict_CV.py `
  --model_dir mfm_results/MT_MFM_moe `
  --data_dir data `
  --folds 1-10 `
  --cache_dir mfm_results/cache_mt
```

```powershell
py MFM/admet/ensemble.py `
  --model_dir mfm_results/MT_MFM_moe `
  --folds 1-10 `
  --cache_dir mfm_results/cache_mt
```

## Example: Single-task (LogD)

```powershell
py MFM/admet/train_ST_MFM.py `
  --target LogD `
  --pretrained_ckpt path/to/ckpt_multitask.pt `
  --output_dir mfm_results/ST_MFM_moe/LogD `
  --data_dir data `
  --folds 1-10 `
  --num_conformers 8 `
  --embedding_mode moe_concat `
  --epochs 400 `
  --patience 40 `
  --batch_size 16 `
  --init_lr 1e-5 `
  --max_lr 3e-4 `
  --final_lr 2e-5 `
  --warmup_epochs 10 `
  --cache_dir mfm_results/cache_st_logd
```

```powershell
py MFM/admet/predict_CV.py `
  --model_dir mfm_results/ST_MFM_moe/LogD `
  --data_dir data `
  --folds 1-10 `
  --cache_dir mfm_results/cache_st_logd
```

```powershell
py MFM/admet/ensemble.py `
  --model_dir mfm_results/ST_MFM_moe/LogD `
  --folds 1-10 `
  --cache_dir mfm_results/cache_st_logd
```

## Outputs

For each fold:

- `fold_i/model_files/best.pt`
- `fold_i/model_files/last.pt`
- `fold_i/summary.json`

Global:

- `train_summary.json`
- `cv_preds.csv` (from `predict_CV.py`)
- `test_ensemble_preds.csv` (from `ensemble.py`)
