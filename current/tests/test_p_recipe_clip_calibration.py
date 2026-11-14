import pytest
from phychem_mfm.phase1.p_recipe_clip import GroupClipCalibration

POLICY=dict(fraction=.05,initial_clip=281.7,quantile=.99)


def test_own_preclip_p99_replaces_initial_threshold_at_exact_five_percent():
    clip=GroupClipCalibration(POLICY,3000000)
    assert clip.threshold==281.7
    for norm,samples in [(10,37500),(20,75000),(30,112500)]:
        assert not clip.observe(norm,samples)
        assert clip.threshold==281.7
    assert clip.observe(1000,150000)
    assert clip.threshold==pytest.approx(970.9)
    assert not clip.observe(1e9,150128)
    assert clip.threshold==pytest.approx(970.9)
    assert clip.fitted_summary()['observed_updates']==4


def test_resume_keeps_the_first_segment_norms_and_fitted_threshold():
    clip=GroupClipCalibration(POLICY,3000000)
    clip.observe(10,50000);clip.observe(20,100000)
    restored=GroupClipCalibration(POLICY,3000000);restored.load_state_dict(clip.state_dict())
    assert restored.threshold==281.7
    restored.observe(1000,150000)
    assert restored.threshold==pytest.approx(980.4)
    frozen=GroupClipCalibration(POLICY,3000000);frozen.load_state_dict(restored.state_dict())
    assert not frozen.observe(2e9,2500000)
    assert frozen.threshold==pytest.approx(980.4)


def test_calibration_does_not_silently_include_samples_after_five_percent():
    with pytest.raises(ValueError,match='exact sample boundary'):
        GroupClipCalibration(POLICY,3000000).observe(10,150001)
