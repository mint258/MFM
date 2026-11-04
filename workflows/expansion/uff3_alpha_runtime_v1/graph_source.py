"""Historical graph-review adapter is inactive under the current key-only policy."""


def raw_source(*args,**kwargs):
    raise RuntimeError('CURRENT_FULLIK_WP5_SOURCE_REQUIRES_ORDERED_CONTRACT_NO_ROOT_GRAPH_REVIEW')