"""Reuse original registry definitions, weighted Spearman and mask codec objects."""
import importlib,sys
from pathlib import Path
from . import contract as C

def objects():
    labels=C.REPO/'workflows/data_v1_final/labels';stream=labels/'streaming_v1';export=C.REPO/'workflows/data_v1_final/export'
    for p in (export,stream,labels):
        if str(p) not in sys.path:sys.path.insert(0,str(p))
    registry=importlib.import_module('build_registry');sys.path.insert(0,str(stream));reduce=importlib.import_module('reduce')
    C.need(Path(registry.__file__).absolute()==labels/'build_registry.py' and Path(reduce.__file__).absolute()==stream/'reduce.py',
      'REAL_ORIGINAL_REGISTRY_AND_RHO_FUNCTION_OBJECTS_NOT_CLONES')
    from workflows.data_v1_final.labels.normalization_v1 import series
    from workflows.data_v1_final.labels.streaming_v1 import compact
    from workflows.data_v1_final.export.pipeline_v1 import masks
    return registry,reduce,series,compact,masks

def exact_series_recipe(series,recipe,*,physical):
    """Select already computed data. No RMS derivation, epsilon or scale fallback."""
    key=recipe['series_key'];C.need(key in series,'ACTUAL_COMPUTED_CALIBRATION_SERIES_NOT_AVAILABLE')
    row=series[key];C.need(row['n']>0 and row['mean'] is not None and row['std_ddof0'] is not None,'CALIBRATION_EMPTY_OR_UNDEFINED')
    C.need(recipe['scale']=='SERIES_STD_DDOF0' and recipe['centering'] in ('SUBTRACT_SERIES_MEAN','FIXED_ZERO'),
      'UNIMPLEMENTED_NORMALIZATION_RECIPE_REQUIRES_REAL_BUILDER_NOT_POLICY_ASSERTION')
    if physical:C.need(recipe['centering']=='FIXED_ZERO' and recipe['per_head_single_scale'] is True,'JOINT_PHYSICAL_SINGLE_SCALE_ZERO_CENTER')
    C.need(row['std_ddof0']>0,'CONSTANT_ZERO_STD_NO_INVENTED_DENOMINATOR_CLOSE_EXPOSURE_OR_RESOLVE_POLICY')
    return {'source_series_key':key,'n':row['n'],'lower':row['lower'],'upper':row['upper'],
      'mean':row['mean'],'std_ddof0':row['std_ddof0'],'centering':recipe['centering'],
      'center_value':0.0 if recipe['centering']=='FIXED_ZERO' else row['mean'],'audit_series_mean':row['mean'],
      'scale_rule':'SERIES_STD_DDOF0','scale':row['std_ddof0'],'per_head_single_scale':physical,
      'winsorization_only_statistical_copies':True,'original_training_labels_modified':False}
