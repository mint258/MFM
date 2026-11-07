"""Full census at write/observer/force/final; bounded per-row census cadence."""
import time
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v3.resource_census import unique_bytes,bind_resource_census,current_root_future
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v3.geometry import ResourceBudget as ORIGINAL
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from . import contract as C
class ResourceBudget(ORIGINAL):
    def __init__(self,*args,**kwargs):
        self.next_row_census=0.;self.row_checks=0;self.full_row_checks=0
        super().__init__(*args,**kwargs)
    def check(self,*,force=False,dispatch=True):
        if force:self.observe()
        if dispatch:C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_PILOT_NO_NEW_WORK_NATURAL_DRAIN')
        self.row_checks+=1;now=time.monotonic()
        if force or now>=self.next_row_census:
            C.need(self.native_census(self.root)+(256<<20)<self.plan['whole_output_cap_bytes'],'FINITE_PILOT_WHOLE_OUTPUT_CAP')
            self.next_row_census=time.monotonic()+1.;self.full_row_checks+=1
    def close(self):
        super().close()
        I.save(self.root/'resource_census_cadence.json',{'schema':'RESOURCE_ONLY_TABLE_ROW_CENSUS_CADENCE_V1','row_checks':self.row_checks,
          'full_row_checks':self.full_row_checks,'maximum_seconds_between_admission_censuses':1.,'full_save_write_observer_force_final_checks_retained':True,
          'original_quota200GB_current_future_RSS_wall_rules_retained':True,'scientific_values_or_quality_rules_changed':False})
