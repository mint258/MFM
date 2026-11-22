"""Fixed, molecule-level cross-fitting and moment-based bootstrap for work A."""
import numpy as np

ALPHAS=np.logspace(-3,3,7)
SEED=20261025

def folds(n,k=5,seed=SEED):
    parts=np.array_split(np.random.default_rng(seed).permutation(n),k)
    return [np.asarray(v,dtype=np.int64) for v in parts]

def _fit(x,y,alpha):
    mx=x.mean(0);sx=x.std(0);sx=np.where(sx>0,sx,1.);my=y.mean(0)
    z=(x-mx)/sx
    return mx,sx,my,np.linalg.solve(z.T@z+alpha*np.eye(z.shape[1]),z.T@(y-my))

def _predict(fit,x):
    mx,sx,my,beta=fit;return (x-mx)/sx@beta+my

def ridge_oof(x,y,outer=None):
    x=np.asarray(x,np.float64);y=np.asarray(y,np.float64)
    if y.ndim==1:y=y[:,None]
    result=np.full_like(y,np.nan);choices=[]
    for i,test in enumerate(folds(len(x)) if outer is None else outer):
        train=np.setdiff1d(np.arange(len(x)),test)
        scores=np.zeros(len(ALPHAS))
        for inner_test in folds(len(train),seed=SEED+i+1):
            validation=train[inner_test];fitrows=np.setdiff1d(train,validation)
            for j,a in enumerate(ALPHAS):
                error=y[validation]-_predict(_fit(x[fitrows],y[fitrows],a),x[validation]);scores[j]+=np.square(error).sum()
        a=float(ALPHAS[int(np.argmin(scores))]);choices.append(a)
        result[test]=_predict(_fit(x[train],y[train],a),x[test])
    return result,choices

def bootstrap_weights(n,repetitions=1000):
    rng=np.random.default_rng(SEED)
    result=np.empty((repetitions,n),np.float64)
    for i in range(repetitions):result[i]=np.bincount(rng.integers(0,n,n),minlength=n)
    return result

def ratio(num,den):
    num=np.asarray(num,np.float64);den=np.asarray(den,np.float64)
    return np.divide(num,den,out=np.full(np.broadcast_shapes(num.shape,den.shape),np.nan),where=den>0)

def total_ss(weights,sums,squares,counts):
    n=weights@counts;s=weights@sums
    return weights@squares-ratio(np.square(s).sum(-1),n)

def cev_values(y,prediction,weights):
    error=np.square(y-prediction).sum(-1)
    denominator=total_ss(weights,y,np.square(y).sum(-1),np.ones(len(y)))
    return 1-ratio(weights@error,denominator)

def conformer_moments(h,owners,n):
    sums=np.zeros((n,h.shape[-1]),np.float64);square=np.zeros(n,np.float64)
    count=np.bincount(owners,minlength=n).astype(np.float64)
    np.add.at(sums,owners,h);np.add.at(square,owners,np.square(h).sum(-1))
    within=np.maximum(square-ratio(np.square(sums).sum(-1),count),0.)
    return sums,square,count,within

def cvf_values(h,owners,prediction,weights):
    sums,square,count,within=conformer_moments(h,owners,len(prediction));valid=count>=2
    count=np.where(valid,count,0.);sums=np.where(valid[:,None],sums,0.);square=np.where(valid,square,0.);within=np.where(valid,within,0.)
    denominator=total_ss(weights,sums,square,count)
    res_sum=sums-count[:,None]*prediction
    res_square=square-2*(prediction*sums).sum(-1)+count*np.square(prediction).sum(-1)
    residual=total_ss(weights,res_sum,res_square,count)
    numerator=weights@within
    return ratio(numerator,denominator),ratio(numerator,residual)

def eev_values(atom_sums,atom_square,atom_counts,atom_owners,elements,weights):
    n=weights.shape[1];sums=np.zeros((n,atom_sums.shape[-1]),np.float64);squares=np.zeros(n,np.float64);counts=np.zeros(n,np.float64)
    np.add.at(sums,atom_owners,atom_sums);np.add.at(squares,atom_owners,atom_square);np.add.at(counts,atom_owners,atom_counts)
    numerator=np.zeros(len(weights),np.float64)
    for z in np.unique(elements):
        use=elements==z;w=weights[:,atom_owners[use]];s=w@atom_sums[use];c=w@atom_counts[use]
        numerator+=np.nan_to_num(ratio(np.square(s).sum(-1),c),nan=0.)
    total_mean=ratio(np.square(weights@sums).sum(-1),weights@counts)
    return ratio(numerator-total_mean,total_ss(weights,sums,squares,counts))

def summary(values):
    point=float(values[0]) if np.isfinite(values[0]) else None;valid=values[1:][np.isfinite(values[1:])]
    return dict(value=point,ci95=np.quantile(valid,[.025,.975]).tolist() if len(valid) else None,valid_bootstrap_replicates=len(valid),reason=None if point is not None else 'Zero variance or unavailable legal comparison')