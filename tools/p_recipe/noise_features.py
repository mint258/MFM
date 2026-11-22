"""A1 original L6/H0 forward with resumable native-record cursor."""
from pathlib import Path
import torch
from finetune import atomic_checkpoint, ContinuationRequired


def produce_features(view,dataset,encoder,output,*,source_identity,should_stop,device="cuda"):
    from torch_geometric.data import Batch,Data
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    complete=output/(dataset+".pt")
    partial=output/(dataset+"_progress.pt")
    identity=dict(source=source_identity,dataset=dataset,layer=6,
                  membership_sha256=view.membership_sha256)
    if complete.exists():
        payload=torch.load(complete,map_location="cpu",weights_only=True)
        if payload["identity"]!=identity:
            raise ValueError("Closed feature source identity changed")
        return payload
    members=[(index,view.get(index,role=role)) for role in
             ("train","train_inner_validation") for index in view.view(role)]
    members=[(index,sample) for index,sample in members if sample.geometry_ready]
    fit=set(view.view("train"));records=[];sizes=[];cursor=0
    if partial.exists():
        saved=torch.load(partial,map_location="cpu",weights_only=True)
        if saved["identity"]!=identity:
            raise ValueError("Partial feature source identity changed")
        records,sizes,cursor=saved["records"],saved["sizes"],saved["cursor"]
        if (len(records)!=cursor or not 0<=cursor<=len(members)
                or [v["member_index"] for v in records]!=[i for i,s in members[:cursor]]):
            raise ValueError("Feature cursor/native record prefix changed")
    def save():
        atomic_checkpoint(partial,dict(identity=identity,records=records,sizes=sizes,cursor=cursor))
    encoder.eval()
    with torch.no_grad():
        while cursor<len(members):
            if should_stop():
                save()
                raise ContinuationRequired("Partial original H0 forward saved")
            selected=members[cursor:cursor+32]
            graph=Batch.from_data_list([Data(x=s.x.reshape(-1,1),pos=s.pos)
                                       for index,s in selected]).to(device)
            atom=encoder.encode_atoms(graph).detach().cpu().float();offset=0
            for index,sample in selected:
                n=len(sample.x)
                records.append(dict(molecule_uid=sample.member_uid,member_index=index,
                    h0=atom[offset:offset+n],source_atom_ids=sample.source_atom_ids))
                if index in fit:sizes.append(n)
                offset+=n
            cursor+=len(selected)
            if cursor%2048==0:
                save()
    if not sizes:
        raise ValueError("Original TRAIN N_ref population is empty")
    payload=dict(identity=identity,records=records,n_ref=sum(sizes)/len(sizes))
    atomic_checkpoint(complete,payload)
    return payload
