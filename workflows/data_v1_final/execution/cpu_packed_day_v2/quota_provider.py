"""Resource-only direct objects from the frozen actual14/18 quota provider."""
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as _original
Client=_original.Client
load_review=_original.load_review
references=_original.references
pinned=_original.pinned
small=_original.small
parse_quota=_original.parse_quota
validate_observation=_original.validate_observation
QUOTA_ARGV=_original.QUOTA_ARGV
def direct_objects():
    return all(globals()[name] is getattr(_original,name) for name in (
        'Client','load_review','references','pinned','small','parse_quota','validate_observation','QUOTA_ARGV'))
