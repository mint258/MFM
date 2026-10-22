"""New task outputs, frozen original inputs, tested repair package first."""
from pathlib import Path
import sys

PROJECT=Path('/share/home/zixiao/descriptor_analysis')
ROOT=PROJECT/'runs/s_denoise_repair_20261016'
OLD=PROJECT/'runs/sprime_s_convergence_20261013'
SOURCE=ROOT/'source_v3'
DEPS=PROJECT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'
# Own workflow directory stays first; scientific package precedes old adapters.
sys.path[1:1]=[str(SOURCE/'current'),str(DEPS),str(SOURCE/'workflows/s_denoise'),str(OLD/'scripts')]
from runtime import sha,save
