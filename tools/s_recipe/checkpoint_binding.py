"""Bind complete S resume states to their original scientific condition."""

SCIENTIFIC_KEYS = ('arm', 'seed', 'samples', 'source', 'noise', 'disabled', 'population',
                   'root', 'batch_size', 'microbatch_size', 'lr', 'betas', 'weight_decay',
                   'clip_calibration', 'distance_bias', 'views', 'components', 'normalization')


def validate_resume(configuration, saved_configuration):
    for key in SCIENTIFIC_KEYS:
        if configuration[key] != saved_configuration[key]:
            raise ValueError('S resume condition differs: '+key)
