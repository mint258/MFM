"""F64 participation ratios with paired molecule-cluster bootstrap weights.

The covariance/participation-ratio definition is the existing P D4 definition.
Per-molecule sufficient statistics allow the taskbook's1000 MID draws without
another encoder forward. Upper-triangle storage and column blocks bound RAM.
"""
import numpy as np


def atom_moments(values):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or not len(values):
        raise ValueError('A nonempty matrix of native atom representations is required')
    upper = np.triu_indices(values.shape[1])
    return len(values), values.sum(axis=0), (values.T@values)[upper]


def participation_ratios(weights, counts, sums, upper_products, *, block_columns=8192):
    """Apply each MID multiplicity to all that molecule's atom observations.

    For mean(H), pass counts=1, sums=mean(H), and its outer products. The first
    row can be all ones for the point estimate; later rows are bootstrap draws.
    A zero covariance has undefined participation ratio and is reported as NaN.
    """
    weights = np.asarray(weights, dtype=np.float64)
    counts = np.asarray(counts, dtype=np.float64)
    sums = np.asarray(sums, dtype=np.float64)
    if sums.ndim != 2 or weights.ndim != 2 or counts.shape != (len(sums),):
        raise ValueError('Molecule weights/counts/sums have incompatible shapes')
    if weights.shape[1] != len(sums) or block_columns < 1:
        raise ValueError('One bootstrap weight per molecule and positive block size required')
    dimension = sums.shape[1]
    left, right = np.triu_indices(dimension)
    if upper_products.shape != (len(sums), len(left)):
        raise ValueError('Upper moments differ from the native representation dimension')
    n = weights@counts
    mean = np.divide(weights@sums, n[:, None],
                     out=np.full((len(weights), dimension), np.nan), where=n[:, None] > 0)
    trace = np.zeros(len(weights), dtype=np.float64)
    square_trace = np.zeros(len(weights), dtype=np.float64)
    for start in range(0, len(left), block_columns):
        stop = min(start+block_columns, len(left))
        i, j = left[start:stop], right[start:stop]
        product = weights@np.asarray(upper_products[:, start:stop], dtype=np.float64)
        covariance = np.divide(product, n[:, None], out=np.full_like(product, np.nan),
                               where=n[:, None] > 0)-mean[:, i]*mean[:, j]
        diagonal = i == j
        trace += covariance[:, diagonal].sum(axis=1)
        # tr(C^2)=||C||_F^2: both symmetric off-diagonal entries count.
        square_trace += (np.square(covariance)*np.where(diagonal, 1., 2.)).sum(axis=1)
    return np.divide(np.square(trace), square_trace, out=np.full_like(trace, np.nan),
                     where=square_trace > 0)
