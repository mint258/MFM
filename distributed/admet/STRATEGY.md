# Strategy Mapping: DMPNN / CheMeleon -> MFM

## Existing baselines

- **ST_DMPNN**: one model per property, no pretrained backbone, random 90/10 train/val split inside each fold.
- **MT_DMPNN**: one shared backbone + multi-task head, task-weighted loss.
- **MT_CheMeleon**: load pretrained message-passing backbone, then train regression head on ADMET tasks.

## MFM alignment in this folder

- **MFM-ST** (`train_ST_MFM.py`): one property per run, same fold data, same 90/10 internal train/val split.
- **MFM-MT** (`train_MT_MFM.py`): all 9 tasks jointly, supports task weights.
- **CheMeleon-like transfer**: load pretrained `MultiTaskMoE` checkpoint and freeze encoder (embedding extractor), then train a lightweight head.
- **Tokenizer idea implemented**:
  - for each SMILES generate `N` RDKit conformers (`--num_conformers`)
  - encode each conformer with MFM backbone
  - average conformer embeddings to build one molecule token
  - tokens form a 2D tensor `[num_molecules, embedding_dim]` for finetuning
  - optional `--embedding_mode moe_concat` uses backbone + MoE expert branches as fused token features
  - optional warmup/cosine LR schedule (`--init_lr/--max_lr/--final_lr/--warmup_epochs`) aligns better with Chemprop training style

## Output compatibility

- Train fold outputs: `fold_i/model_files/best.pt`
- CV prediction: `cv_preds.csv`
- Ensemble prediction: `test_ensemble_preds.csv`
