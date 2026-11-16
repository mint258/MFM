"""F64 molecular moments and the preregistered D0 selection, without fitting D4."""
import numpy as np


def molecular_moments(values):
    values=np.asarray(values,np.float64)
    valid=np.isfinite(values);count=valid.sum(0)
    mean=np.divide(np.where(valid,values,0).sum(0),count,
        out=np.full(values.shape[1],np.nan),where=count>0)
    within=np.where(valid,values-mean,0)
    return mean,count,np.square(within).sum(0)


class TrainMoments:
    def __init__(self,width):
        self.n=np.zeros(width,np.int64);self.mean=np.zeros(width)
        self.m2=np.zeros(width);self.within=np.zeros(width)
        self.multi=np.zeros(width,np.int64);self.conformers=np.zeros(width,np.int64)
    def add(self,mean,count,within):
        valid=np.isfinite(mean);nb=valid.sum(0)
        mb=np.divide(np.where(valid,mean,0).sum(0),nb,out=np.zeros_like(self.mean),where=nb>0)
        m2b=np.square(np.where(valid,mean-mb,0)).sum(0)
        total=self.n+nb;delta=mb-self.mean
        self.mean+=np.divide(delta*nb,total,out=np.zeros_like(delta),where=total>0)
        self.m2+=m2b+np.divide(delta**2*self.n*nb,total,out=np.zeros_like(delta),where=total>0)
        self.n=total;multi=count>=2
        self.multi+=multi.sum(0);self.conformers+=np.where(multi,count,0).sum(0)
        self.within+=np.where(multi,within,0).sum(0)
    def result(self,n_molecules,errors,names):
        s1=np.sqrt(np.divide(self.m2,self.n,out=np.full(len(names),np.nan),where=self.n>0))
        s2=np.sqrt(np.divide(self.within,self.conformers,out=np.full(len(names),np.nan),where=self.conformers>0))
        result={}
        for i,name in enumerate(names):
            e=float(errors[name]);fraction=float(self.multi[i]/n_molecules)
            good=np.isfinite(s1[i]) and s1[i]>0 and np.isfinite(s2[i])
            selected=bool(good and fraction>=.5 and s2[i]>=.001*s1[i] and s2[i]>=10*e)
            result[name]=dict(c1=float(self.mean[i]) if self.n[i] else None,
                s1=float(s1[i]) if np.isfinite(s1[i]) else None,
                s2=float(s2[i]) if np.isfinite(s2[i]) else None,
                valid_mu_molecules=int(self.n[i]),multi_valid_molecules=int(self.multi[i]),
                multi_valid_fraction=fraction,multi_valid_conformers=int(self.conformers[i]),
                median_F32_difference_error=e,s2_over_s1=float(s2[i]/s1[i]) if good else None,
                s2_over_error=float(s2[i]/e) if np.isfinite(s2[i]) and e>0 else None,
                selected=selected,reason=None if selected else 'Preregistered eligibility not met or undefined scale')
        return result