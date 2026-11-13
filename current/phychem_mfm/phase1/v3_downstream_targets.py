"""User-requested QM9 atomization target and report-only SoM, inactive in v2."""
from __future__ import annotations

from dataclasses import replace
import math
from numbers import Integral

# Original QM9 Atomref file3195395, U(0K) column, Hartree.
# https://ndownloader.figshare.com/files/3195395
QM9_U0_ATOMREF_HA={1:-.500273,6:-37.846772,7:-54.583861,8:-75.064579,9:-99.718730}
ATOMIZATION_TASK_ID='qm9.U0_atom'
REPORT_ONLY_TASK_IDS=('cyp.3A4','cyp.2D6')
PRIMARY_TASK_IDS=('exp.LogD','exp.Log_HLM_CLint','exp.LogS',
 ATOMIZATION_TASK_ID,'qm9.homo','qm9.lumo','qm9.alpha')

def qm9_u0_atomization(u0,element_ids,*,element_index_base):
 """U0-sum(atom references),including every native H; no per-atom division."""
 if element_index_base not in (0,1):
  raise ValueError('Explicit zero-based element IDs or one-based atomic numbers required')
 ids=tuple(element_ids)
 if not ids or any(not isinstance(value,Integral) for value in ids):
  raise ValueError('Nonempty complete native integer element sequence required')
 atomic_numbers=tuple(int(value)+(1 if element_index_base==0 else 0) for value in ids)
 if any(z not in QM9_U0_ATOMREF_HA for z in atomic_numbers):
  raise ValueError('QM9 target requires native H/C/N/O/F atoms; no padding or inferred H')
 value=float(u0)
 if not math.isfinite(value):
  raise ValueError('An observed finite source U0 is required')
 return value-math.fsum(QM9_U0_ATOMREF_HA[z] for z in atomic_numbers)

def atomization_rows(view,cached_h0,task,*,role):
 """Transform selected TRAIN rows only; original packed targets remain intact."""
 import torch
 from .v3_dev_evaluation import task_rows
 if (task.task_id!=ATOMIZATION_TASK_ID or task.dataset_id!='qm9'
     or task.field!='U0' or task.output_level!='graph'):
  raise ValueError('Explicit QM9 U0-atomization task required')
 rows=task_rows(view,cached_h0,task,role=role)
 by_uid={row.source_member_uid:row for row in rows}
 targets={}
 for index in view.view(role):
  sample=view.get(index,role=role)
  if sample.member_uid not in by_uid:
   continue
  row=by_uid[sample.member_uid]
  # Source elements are zero based,source IDs cover all native atoms,including H.
  if len(sample.x)!=len(row.h0):
   raise ValueError('Complete source element count and frozen H0 atom count differ')
  values=row.targets.to(torch.float64).clone()
  if bool(row.supervision_mask[0]):
   values[0]=qm9_u0_atomization(float(values[0]),sample.x.cpu().tolist(),
    element_index_base=0)
  targets[sample.member_uid]=values
 return tuple(replace(row,targets=targets[row.source_member_uid]) for row in rows)

def compare_report_only_panel(candidate,reference,**kwargs):
 """Seven molecular tasks decide; SoM keeps separate metrics and intervals."""
 from .v3_dev_evaluation import compare_panel
 expected=set(PRIMARY_TASK_IDS)|set(REPORT_ONLY_TASK_IDS)
 if set(candidate)!=expected or set(reference)!=expected:
  raise ValueError('Require exact seven molecular and two report-only SoM tasks')
 main=compare_panel({key:candidate[key] for key in PRIMARY_TASK_IDS},
  {key:reference[key] for key in PRIMARY_TASK_IDS},**kwargs)
 report=compare_panel({key:candidate[key] for key in REPORT_ONLY_TASK_IDS},
  {key:reference[key] for key in REPORT_ONLY_TASK_IDS},**kwargs)
 report['selection_use']=False
 main.update(panel='v3',primary_task_ids=list(PRIMARY_TASK_IDS),
  report_only_task_ids=list(REPORT_ONLY_TASK_IDS),report_only=report,
  primary_task_count=7,SoM_selection_use=False)
 return main
