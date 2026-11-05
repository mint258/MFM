"""Direct original codec and exact calibration objects, with actual source pins."""
from pathlib import Path
from ..portable_sources_v1.transport import verify
from .inventory import need


def load(plan):
    from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec
    from workflows.data_v1_final.labels.streaming_v1 import calibration,compact
    from workflows.data_v1_final.labels.lossless_projection_pilot_v1 import projection
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support
    modules={'codec':codec,'calibration':calibration,'compact':compact,'projection':projection,'owner_support':support}
    for name,module in modules.items():
        need(Path(module.__file__).resolve()==verify(plan['scientific_sources'][name]).resolve(),'Exact deployed original source required:'+name)
    need(codec.B.RadixCounts is calibration.RadixCounts and codec.B.train_values is calibration.train_values
         and codec.B.encode is projection.encode and codec.B.decode is projection.decode and codec.B.compact is compact,
         'Direct original function identities required; no statistical or codec copy')
    return codec,calibration,support
