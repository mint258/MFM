"""Retain selected new FT models after proven completion; never touch P files."""
import json
import os
from pathlib import Path
import stat

from storage_20261122 import CONTROL, write


def require_closed(summary, closure):
    if (summary.get('status') != 'COMPLETE' or closure.get('status') != 'COMPLETE'
            or closure.get('exit_code') != 0 or not closure.get('owned_descendants_exited')
            or not closure.get('observer_joined')):
        raise ValueError('Only a fully completed fit with actual owned exit may be sealed')


def selected_payload(state):
    if (state.get('epoch') != 50 or state.get('phase') != 'train'
            or state.get('offset') != 0 or state.get('order') != []
            or not state.get('best_encoder') or not state.get('best_head')
            or not isinstance(state.get('selected_epoch'), int)):
        raise ValueError('A completed50-epoch selected fullFT state is required')
    return dict(schema='S_FULLFT_SELECTED_V1', encoder=state['best_encoder'],
        head=state['best_head'], normalization=state['normalization'],
        initial_architecture=state['initial_architecture'], identity=state['identity'],
        selected_epoch=state['selected_epoch'], best_internal_mae=state['best_error'])


def same_execution(summary,closure):
    if closure['job_id'] is not None:
        return summary.get('job_id')==str(closure['job_id'])
    execution=summary.get('native_execution',{})
    producer=execution.get('producer',{})
    actual=closure.get('producer',{})
    return (summary.get('job_id') is None and execution.get('native_handle') is not None
        and execution['native_handle']==closure.get('native_handle')
        and execution.get('run')==closure.get('run')
        and execution.get('node')==closure.get('node')
        and all(producer.get(key) is not None and producer[key]==actual.get(key)
                for key in ('pid','uid','start_ticks')))


def seal(output, closure_path):
    output = Path(output)
    if (output.parent != CONTROL/'finetune_20261124' or output.resolve()!=output
            or output.stat().st_uid != os.getuid()):
        raise ValueError('Only canonical owned new S fullFT outputs may be sealed')
    receipt_path = output/'selected_model_receipt.json'
    if receipt_path.exists():
        return json.loads(receipt_path.read_text())
    summary = json.loads((output/'summary.json').read_text())
    closure = json.loads(Path(closure_path).read_text())
    require_closed(summary, closure)
    if not same_execution(summary,closure):
        raise ValueError('Complete producer summary and actual owned closure job differ')
    source = output/'complete_state.pt'
    observed = source.lstat()
    if (not stat.S_ISREG(observed.st_mode) or observed.st_uid != os.getuid()
            or observed.st_nlink != 1):
        raise ValueError('Continuation state must be one regular owned unlinked file')
    import torch
    state = torch.load(source, map_location='cpu', weights_only=True)
    selected = selected_payload(state)
    if selected['selected_epoch'] != summary['detail']['selected_epoch']:
        raise ValueError('Selected artifact does not match the original completed evaluation')
    destination = output/'selected_model.pt'
    if destination.exists() or destination.is_symlink():
        raise ValueError('Existing selected artifact requires its original receipt, no overwrite')
    pending = output/'selected_model.pt.new'
    if pending.exists() or pending.is_symlink():
        raise ValueError('Unfinished prior selected artifact must be reviewed')
    torch.save(selected, pending)
    with pending.open('rb') as stream:
        os.fsync(stream.fileno())
    pending.replace(destination)
    directory = os.open(output, os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    current = source.lstat()
    if (current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns) != (
            observed.st_dev,observed.st_ino,observed.st_size,observed.st_mtime_ns):
        raise ValueError('Completed source state changed before retirement')
    receipt = dict(status='SELECTED_MODEL_DURABLE_CONTINUATION_RETIRED',
        selected_model=str(destination), selected_bytes=destination.stat().st_size,
        source_continuation=str(source), source_bytes=observed.st_size,
        original_summary=str(output/'summary.json'), owned_exit_evidence=str(closure_path),
        selected_epoch=selected['selected_epoch'], predictions_unchanged=True,
        reason='completed producer cannot resume; selected best encoder/head and normalization retained')
    # Exact canonical own continuation file only, after durable selected model.
    source.unlink()
    write(receipt_path, receipt)
    return receipt
