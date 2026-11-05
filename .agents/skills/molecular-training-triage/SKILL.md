---
name: molecular-training-triage
description: Use when analyzing, debugging, or comparing molecular representation learning, molecular foundation-model fine-tuning, ADMET/QSAR benchmarks, or Stage DEF/Stage B training results. Bias diagnosis toward architecture, representation, data preprocessing, label transforms, split semantics, and feature construction before optimizer or checkpoint-tuning explanations.
---

# Molecular Training Triage

When analyzing molecular representation learning, ADMET/QSAR fine-tuning, or benchmark discrepancies, use this prior:

- Treat network architecture, representation level, pooling/readout design, target/label transformation, dataset preprocessing, split construction, conformer generation, feature construction, and evaluation semantics as the most likely sources of meaningful performance differences.
- Treat optimizer choice, small learning-rate changes, batch-size tweaks, early stopping versus final checkpoint, and similar training-strategy details as secondary explanations unless there is direct evidence they dominate.
- Do not over-attribute observed differences to hyperparameter tuning. First ask whether the models are consuming the same molecular information, predicting in the same target space, using comparable readout heads, and being evaluated under the same split and metric semantics.
- For foundation-model fine-tuning, inspect the gradient path and trainable parameter set: frozen embeddings, partial unfreeze, full fine-tune, LoRA/adapters, native model heads, and cached versus live backbone execution are architectural/training-graph differences, not mere tuning details.
- Still mention optimizer/checkpoint strategy when it changes the scientific comparison, but frame it as a lower-priority hypothesis unless logs, ablations, or failed convergence make it central.

Practical diagnosis order:

1. Verify dataset identity, split semantics, label units, transforms, missing-label masks, and metric computation.
2. Compare representation inputs: 2D graph, 3D conformers, atom tokens, graph embeddings, descriptor fusion, cache path, and invalid-molecule fallback behavior.
3. Compare model architecture and readout: encoder family, pooling, prediction head, uncertainty/evidential output, multitask layout, and target-space conversion.
4. Compare gradient flow: which backbone modules receive gradients, whether features are cached, and whether the training graph is truly end-to-end.
5. Only then evaluate optimizer, learning-rate schedule, batch size, early stopping, checkpoint selection, and other tuning choices.
