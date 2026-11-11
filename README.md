# Complete offline W&B archives

P/C1-b seed0 completed 6,000,000 cumulative samples. The three actual execution segments (4526378 → 4529098 → 4529110) and their paired diagnostics SDK runs are closed. This archive contains all 110 regular files in those six run directories, including native .wandb files, step histories, 1000-update means, system observations, snapshots and original completion/provenance metadata. Original server files remain unchanged. SDK navigation symlinks are omitted; their target regular files are included.

Compressed size: 30,209,948 bytes. Uncompressed regular-file size: 216,239,653 bytes. No model checkpoint or scientific data export is included.

Clone this archive branch and reconstruct the file:

```bash
git clone --single-branch --branch model-v3-wandb-archives-20261111 https://github.com/mint258/MFM.git MFM-wandb
cd MFM-wandb/P_C1_b_seed0
cat P_C1_b_seed0_complete_wandb.tar.gz.part?? > P_C1_b_seed0_complete_wandb.tar.gz
tar -xzf P_C1_b_seed0_complete_wandb.tar.gz
```

The ten parts are ordered part01 through part10; concatenation restores the original gzip archive exactly. See P_C1_b_seed0/manifest.json for source paths, file sizes and per-part sizes. Recovered native SDK directories are WANDB_20261110/{4526378,4529098,4529110}/wandb and WANDB_20261110/diagnostics/{4526378,4529098,4529110}/wandb. W&B cloud synchronization was not completed; upload here preserves the complete offline run files.

C1-0 remains training and will be archived after its corresponding SDK executions close.

P/C1-a seed0 also completed 6,000,000 cumulative samples. Executions 4526377 → 4529097 → 4529109 and their paired diagnostics SDK runs are all closed. Its complete archive contains 110 regular files, compressed to 30,929,928 bytes (224,501,103 regular-file bytes before compression). Original files are retained.

After cloning the same branch, reconstruct C1-a with:

```bash
cd MFM-wandb/P_C1_a_seed0
cat P_C1_a_seed0_complete_wandb.tar.gz.part?? > P_C1_a_seed0_complete_wandb.tar.gz
tar -xzf P_C1_a_seed0_complete_wandb.tar.gz
```

See P_C1_a_seed0/manifest.json for the complete file/part inventory. Both candidates retain native offline SDK histories, 1000-update means, system observations and original execution provenance. These archives do not imply a joint architecture winner.
