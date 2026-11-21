"""Bind complete S resume states to their original scientific condition."""

SCIENTIFIC_KEYS = ('arm', 'seed', 'samples', 'source', 'noise', 'disabled', 'population',
                   'root', 'batch_size', 'microbatch_size', 'lr', 'betas', 'weight_decay',
                   'clip_calibration', 'distance_bias', 'views', 'components', 'normalization')


def validate_resume(configuration, saved_configuration):
    for key in SCIENTIFIC_KEYS:
        if configuration[key] != saved_configuration[key]:
            raise ValueError('S resume condition differs: '+key)


def baseline_acceptance_required(c, samples_consumed, validation_pass=False):
    """The one acceptance belongs to the original3M seed0 baseline only."""
    return (c['arm'] == 'S-B0' and c['seed'] == 0 and c['samples'] == 3000000
            and samples_consumed == 0 and not validation_pass
            and 'baseline_acceptance' not in c)
