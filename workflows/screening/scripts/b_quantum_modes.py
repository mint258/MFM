"""Small vibrational-mode diagnostics; matrices are not persistent labels."""
import itertools
import math
import re
from pathlib import Path
import numpy as np

FLOAT=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'
def number(x):return float(x.replace('D','E').replace('d','e'))
def xyz(path,symbols):
    lines=Path(path).read_text().splitlines();n=int(lines[0]);rows=[line.split() for line in lines[2:2+n]]
    if n!=len(symbols) or [row[0] for row in rows]!=list(symbols):raise ValueError('OUTPUT_ATOM_ORDER_MISMATCH')
    return np.asarray([[float(x) for x in row[1:4]] for row in rows])
def aligned_rmsd(reference,coords,indices=None):
    if indices is not None:reference,coords=reference[indices],coords[indices]
    a=reference-reference.mean(axis=0);b=coords-coords.mean(axis=0)
    u,s,vh=np.linalg.svd(b.T@a);rotation=u@np.diag([1,1,np.linalg.det(u@vh)])@vh
    return float(np.sqrt(np.mean(np.sum((b@rotation-a)**2,axis=1))))
def gaussian_modes(path,symbols):
    lines=Path(path).read_text(errors='replace').splitlines();freqs=[];modes=[];n=len(symbols)
    for index,line in enumerate(lines):
        if 'Frequencies --' not in line:continue
        tokens=line.split('--',1)[1].split()
        try:values=[number(x) for x in tokens]
        except ValueError:continue
        start=next((j for j in range(index+1,min(index+20,len(lines))) if re.match(r'\s*Atom\s+AN\s+',lines[j])),None)
        if start is None:continue
        rows=[]
        for data in lines[start+1:start+1+n]:
            tok=data.split()
            if len(tok)!=2+3*len(values) or not tok[0].isdigit():break
            rows.append([number(x) for x in tok[2:]])
        if len(rows)==n:
            array=np.asarray(rows).reshape(n,len(values),3)
            freqs.extend(values);modes.extend(array.transpose(1,0,2))
    return np.asarray(freqs),np.asarray(modes)
def force_aux(path):
    text=Path(path).read_text(errors='replace')
    hits=list(re.finditer(r'(?m)^\s*([A-Z][A-Z0-9_:./() -]*?)(?:\[(\d+)\])?\s*=\s*',text));data={}
    for i,hit in enumerate(hits):
        key=hit.group(1).strip()
        if key not in ('VIB._FREQ:CM(-1)','NORMAL_MODES','ZERO_POINT_ENERGY:KCAL/MOL','ISOTOPIC_MASSES',
                       'HEAT_OF_FORMATION:KCAL/MOL','GRADIENT_NORM:KCAL/MOL/ANGSTROM',
                       'ATOM_X:ANGSTROMS','ATOM_X_OPT:ANGSTROMS'):continue
        body=text[hit.end():hits[i+1].start() if i+1<len(hits) else len(text)]
        tokens='\n'.join(line for line in body.splitlines() if not line.lstrip().startswith('#')).split()
        count=int(hit.group(2)) if hit.group(2) else 1
        data[key]=[number(x) for x in tokens[:count]]
    return data
def torsion_metrics(coords,z,modes,frequencies):
    """Exploratory normalized internal-coordinate change scores, not energy fractions."""
    from rdkit import Chem
    pt=Chem.GetPeriodicTable();radii=np.asarray([pt.GetRcovalent(int(atom)) for atom in z]);n=len(z)
    bonds=[(i,j) for i in range(n) for j in range(i) if 0.3<np.linalg.norm(coords[i]-coords[j])<1.25*(radii[i]+radii[j])]
    adj=[set() for _ in z]
    for i,j in bonds:adj[i].add(j);adj[j].add(i)
    angles=[(i,j,k) for j in range(n) for i,k in itertools.combinations(sorted(adj[j]),2)]
    torsions=[]
    for j,k in bonds:
        if z[j]==1 or z[k]==1:continue
        visited={j};queue=[j]
        while queue:
            v=queue.pop()
            for neighbor in adj[v]:
                if {v,neighbor}=={j,k} or neighbor in visited:continue
                visited.add(neighbor);queue.append(neighbor)
        if k in visited:continue
        for i in adj[j]-{k}:
            for l in adj[k]-{j}:torsions.append((i,j,k,l))
    def angle(c,t):
        i,j,k=t;a=c[i]-c[j];b=c[k]-c[j]
        return math.acos(float(np.clip(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)),-1,1)))
    def dihedral(c,t):
        i,j,k,l=t;a=c[i]-c[j];b=c[k]-c[j];d=c[l]-c[k];b=b/np.linalg.norm(b)
        v=a-np.dot(a,b)*b;w=d-np.dot(d,b)*b
        return math.atan2(float(np.dot(np.cross(b,v),w)),float(np.dot(v,w)))
    result=[]
    for mode,frequency in zip(modes,frequencies):
        if frequency>=-20:continue
        norm=float(np.linalg.norm(mode))
        if not norm:continue
        step=mode*(0.001/norm);plus=coords+step;minus=coords-step
        stretch=[((np.linalg.norm(plus[i]-plus[j])-np.linalg.norm(minus[i]-minus[j]))/0.002)**2 for i,j in bonds]
        bend=[((angle(plus,t)-angle(minus,t))/0.002*np.linalg.norm(coords[t[0]]-coords[t[1]]))**2 for t in angles]
        twist=[((dihedral(plus,t)-dihedral(minus,t)+math.pi)%(2*math.pi)-math.pi)/0.002*np.linalg.norm(coords[t[1]]-coords[t[2]]) for t in torsions]
        scores=[float(np.mean(stretch)) if stretch else 0.,float(np.mean(bend)) if bend else 0.,float(np.mean(np.square(twist))) if twist else 0.]
        total=sum(scores);share=scores[2]/total if total else None
        result.append({'frequency_cm_inverse':float(frequency),'stretch_score':scores[0],'bend_score':scores[1],
                       'torsion_score':scores[2],'torsion_score_share':share,'torsion_dominant_heuristic':share is not None and share>0.5})
    return {'status':'AVAILABLE' if len(modes) else 'NO_MODE_VECTORS','negative_mode_metrics':result,
            'bond_count':len(bonds),'angle_count':len(angles),'bridge_dihedral_count':len(torsions),
            'interpretation':'Heuristic finite-displacement internal-coordinate scores; not kinetic/potential energy fractions. Connectivity from 1.25*covalent-radius sum, bridge torsions only.'}
