"""Compare new cluster sufficient statistics with explicit F64 resampling."""
import numpy as np

from representation_moments import atom_moments, participation_ratios


def test_atom_bootstrap_matches_explicit_repeated_molecules_in_f64():
    rng = np.random.default_rng(20261025)
    clusters = [rng.normal(size=(n, 4))+offset for n, offset in ((5, 0.), (3, 2.), (7, -.5))]
    moments = [atom_moments(v) for v in clusters]
    weights = np.asarray([[1, 1, 1], [2, 0, 1], [0, 3, 0]], dtype=np.float64)
    actual = participation_ratios(weights, np.asarray([v[0] for v in moments]),
        np.stack([v[1] for v in moments]), np.stack([v[2] for v in moments]), block_columns=3)
    expected = []
    for draw in weights.astype(int):
        atoms = np.concatenate([v for count, v in zip(draw, clusters) for _ in range(count)])
        centered = atoms-atoms.mean(axis=0)
        covariance = centered.T@centered/len(atoms)
        eigenvalues = np.linalg.eigvalsh(covariance)
        expected.append(eigenvalues.sum()**2/np.square(eigenvalues).sum())
    np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=1e-10)


def test_constant_representation_has_undefined_participation_ratio():
    moments = atom_moments(np.ones((3, 4)))
    actual = participation_ratios(np.ones((1, 1)), np.asarray([moments[0]]),
        moments[1][None, :], moments[2][None, :], block_columns=3)
    assert np.isnan(actual[0])
