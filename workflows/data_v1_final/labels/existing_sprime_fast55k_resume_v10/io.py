"""Restore the original writer's keyword defaults in its private function copy."""
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v6 import io as OLD
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as ORIGINAL

def writer_function():
    value=OLD.writer_function()
    value.__kwdefaults__=ORIGINAL.write_parquet.__kwdefaults__
    return value

def proof():
    value=writer_function();original=ORIGINAL.write_parquet
    assert value.__code__ is original.__code__
    assert value.__defaults__==original.__defaults__
    assert value.__kwdefaults__==original.__kwdefaults__
    assert value.__kwdefaults__['row_group_size']==256
    return dict(original_entire_writer_code_and_all_defaults_retained=True,
      row_group_size_from_original_keyword_default=256,
      original_raw_encoder_and_full_semantic_readback=OLD.proof())
