"""Per-arm clipping; fixed sample-window policy and legacy resume support."""
import math
import numpy as np


class GroupClipCalibration:
    def __init__(self,policy,sample_budget):
        self.fixed_window='window_start_samples' in policy
        self.calibration_samples=int(policy['calibration_samples']) if self.fixed_window else math.ceil(sample_budget*policy['fraction'])
        self.window_start_samples=int(policy['window_start_samples']) if self.fixed_window else 0
        self.quantile=float(policy['quantile'])
        self.initial_clip=float(policy['initial_clip'])
        self.threshold=self.initial_clip
        self.norms=[]
        self.fitted=False
        self.effective_freeze_samples=None

    @property
    def exact_boundary(self):
        return not self.fixed_window

    def observe(self,norm,samples_consumed,*,samples_before=None):
        if self.fitted:return False
        if self.fixed_window:
            if samples_before is None:raise ValueError('Fixed clipping needs the complete step sample cursor')
            if self.window_start_samples<=samples_before<self.calibration_samples:
                self.norms.append(float(norm))
            complete=samples_consumed>=self.calibration_samples
        else:
            if samples_consumed>self.calibration_samples:
                raise ValueError('Clip calibration must end at the exact sample boundary')
            self.norms.append(float(norm))
            complete=samples_consumed==self.calibration_samples
        if complete:
            if not self.norms:raise ValueError('No preclip norms in the registered calibration window')
            self.threshold=float(np.quantile(self.norms,self.quantile))
            self.fitted=True
            self.effective_freeze_samples=int(samples_consumed)
            return True
        return False

    def state_dict(self):
        result=dict(calibration_samples=self.calibration_samples,quantile=self.quantile,
                    initial_clip=self.initial_clip,threshold=self.threshold,
                    norms=list(self.norms),fitted=self.fitted)
        if self.fixed_window:
            result.update(window_start_samples=self.window_start_samples,
                          sample_axis='optimizer_step_start',effective_freeze_samples=self.effective_freeze_samples)
        return result

    def load_state_dict(self,state):
        for key in ('calibration_samples','quantile','initial_clip'):
            if state[key]!=getattr(self,key):raise ValueError('Clip calibration configuration changed on resume')
        if self.fixed_window and state.get('window_start_samples')!=self.window_start_samples:
            raise ValueError('Clip calibration window changed on resume')
        self.threshold=float(state['threshold']);self.norms=list(state['norms']);self.fitted=bool(state['fitted'])
        self.effective_freeze_samples=state.get('effective_freeze_samples')

    def fitted_summary(self):
        result=dict(calibration_samples=self.calibration_samples,quantile=self.quantile,
                    initial_clip=self.initial_clip,threshold=self.threshold,
                    observed_updates=len(self.norms),fitted=self.fitted)
        if self.fixed_window:
            result.update(window_start_samples=self.window_start_samples,
                          sample_axis='optimizer_step_start',effective_freeze_samples=self.effective_freeze_samples)
        return result
