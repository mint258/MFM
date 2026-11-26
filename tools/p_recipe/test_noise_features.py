"""Resume original H0 generation without replaying completed native records."""
from types import SimpleNamespace
import torch
import pytest
from noise_features import produce_features
from finetune import ContinuationRequired


class View:
    membership_sha256="same-original-members"
    def view(self,role):
        return tuple(range(64)) if role=="train" else tuple(range(64,80))
    def get(self,index,*,role):
        n=2+index%3
        return SimpleNamespace(member_uid="source"+str(index),x=torch.arange(n),
            pos=torch.arange(n*3).float().reshape(n,3)/7,geometry_ready=True,
            source_atom_ids=torch.arange(n))


class Encoder:
    def __init__(self):self.calls=0
    def eval(self):return self
    def encode_atoms(self,batch):
        self.calls+=1
        return batch.x.float().repeat(1,512)+batch.pos.sum(1,keepdim=True)


def test_feature_resume_keeps_original_atom_order_and_skips_closed_prefix(tmp_path):
    direct_encoder,first_encoder,resume_encoder=Encoder(),Encoder(),Encoder()
    direct=produce_features(View(),"qm9",direct_encoder,tmp_path/"direct",
        source_identity={"checkpoint":"one"},should_stop=lambda:False,device="cpu")
    with pytest.raises(ContinuationRequired):
        produce_features(View(),"qm9",first_encoder,tmp_path/"resumed",
            source_identity={"checkpoint":"one"},should_stop=lambda:first_encoder.calls>=1,device="cpu")
    actual=produce_features(View(),"qm9",resume_encoder,tmp_path/"resumed",
        source_identity={"checkpoint":"one"},should_stop=lambda:False,device="cpu")
    assert direct_encoder.calls==first_encoder.calls+resume_encoder.calls==3
    assert actual["n_ref"]==direct["n_ref"]
    assert len(actual["records"])==len(direct["records"])==80
    for a,b in zip(actual["records"],direct["records"]):
        assert a["member_index"]==b["member_index"]
        assert torch.equal(a["source_atom_ids"],b["source_atom_ids"])
        assert torch.equal(a["h0"],b["h0"])


def test_closed_feature_reuse_never_starts_another_forward_and_binds_checkpoint(tmp_path):
    encoder=Encoder()
    produce_features(View(),"qm9",encoder,tmp_path,
        source_identity={"checkpoint":"one"},should_stop=lambda:False,device="cpu")
    reused=Encoder()
    produce_features(View(),"qm9",reused,tmp_path,
        source_identity={"checkpoint":"one"},should_stop=lambda:False,device="cpu")
    assert reused.calls==0
    with pytest.raises(ValueError,match="identity"):
        produce_features(View(),"qm9",reused,tmp_path,
            source_identity={"checkpoint":"different"},should_stop=lambda:False,device="cpu")
