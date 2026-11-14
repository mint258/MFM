"""The user's per-group first-five-percent preclip-norm calibration."""
import math
import numpy as np


class GroupClipCalibration:
    def __init__(self,policy,sample_budget):
        self.calibration_samples=math.ceil(sample_budget*policy['fraction'])
        self.quantile=float(policy['quantile'])
        self.initial_clip=float(policy['initial_clip'])
        self.threshold=self.initial_clip
        self.norms=[]
        self.fitted=False

    def observe(self,norm,samples_consumed):
        if self.fitted:return False
        if samples_consumed>self.calibration_samples:
            raise ValueError('Clip calibration must end at the exact sample boundary')
        self.norms.append(float(norm))
        if samples_consumed==self.calibration_samples:
            self.threshold=float(np.quantile(self.norms,self.quantile))
            self.fitted=True
            return True
        return False

    def state_dict(self):
        return dict(calibration_samples=self.calibration_samples,quantile=self.quantile,
                    initial_clip=self.initial_clip,threshold=self.threshold,
                    norms=list(self.norms),fitted=self.fitted)

    def load_state_dict(self,state):
        for key in ('calibration_samples','quantile','initial_clip'):
            if state[key]!=getattr(self,key):raise ValueError('Clip calibration configuration changed on resume')
        self.threshold=float(state['threshold']);self.norms=list(state['norms']);self.fitted=bool(state['fitted'])

    def fitted_summary(self):
        return dict(calibration_samples=self.calibration_samples,quantile=self.quantile,
                    initial_clip=self.initial_clip,threshold=self.threshold,
                    observed_updates=len(self.norms),fitted=self.fitted)
