"""A1 must reuse seed0 and the separate round4 F2 own-budget checkpoint."""
import pytest
from noise_entry import validate_configuration


def configuration():
    specs=[("T2_1M","T2",1000000,9000000),
           ("T2_6M","T2",6000000,9000000),
           ("T2_9M","T2",9000000,9000000),
           ("round4_F2","F2",3000000,3000000)]
    return dict(sources=[dict(label=label,source_binding=dict(arm=arm,samples=samples,
        source_training_budget=budget)) for label,arm,samples,budget in specs],
        readout_seeds=[1,2,3,4],layer=6,timebox_seconds=14400,new_pretraining=False)


def test_midpoint_of_9M_cannot_replace_round4_F2_own_3M():
    c=configuration();validate_configuration(c)
    c["sources"][-1]["source_binding"]=dict(arm="T2",samples=3000000,source_training_budget=9000000)
    with pytest.raises(ValueError,match="own3M"):
        validate_configuration(c)


def test_existing_seed0_is_never_refitted_as_a_new_noise_seed():
    c=configuration();c["readout_seeds"]=[0,1,2,3,4]
    with pytest.raises(ValueError,match="seeds0 reuse"):
        validate_configuration(c)
