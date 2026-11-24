"""E1 opt-in training cap; use the published fixed-random order unchanged."""

def training_conformer_cap(configuration, *, validation=False):
    cap = configuration.get("conformer_cap")
    if cap is None:
        return 10
    if type(cap) is not int or cap not in (1, 2, 5, 10):
        raise ValueError("E1 conformer_cap must be one of 1,2,5,10")
    if configuration.get("source") != "PM7" or configuration.get("order", "fixed_random") != "fixed_random":
        raise ValueError("E1 uses only the published PM7 fixed_random order")
    # Keep the original fixed VAL population/conformer and loss definition.
    return 10 if validation else cap
