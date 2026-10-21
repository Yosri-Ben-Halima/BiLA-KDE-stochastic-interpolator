import itertools

import numpy as np


def scores(chains, truth, seed):
    """Missing coordinates only; pair expectations use independent chain groups."""
    chains = np.asarray(chains)
    truth = np.asarray(truth)
    flat = chains.reshape(-1, len(truth))
    rng = np.random.default_rng(seed)
    distance = np.linalg.norm(flat - truth, axis=1)
    pairs = list(itertools.combinations(range(4), 2))
    pair_energy, pair_crps, pair_variance = [], [], []
    for j, (first_group, second_group) in enumerate(pairs):
        count = 4096 // 6 + (j < 4096 % 6)
        first = chains[first_group, rng.integers(0, chains.shape[1], count)]
        second = chains[second_group, rng.integers(0, chains.shape[1], count)]
        norms = np.linalg.norm(first - second, axis=1)
        pair_energy.append(norms.mean())
        pair_crps.append(np.abs(first - second).mean())
        pair_variance.append(norms.var(ddof=1) / count)
    energy = (distance.mean() - 0.5 * np.mean(pair_energy)) / np.sqrt(len(truth))
    crps = np.abs(flat - truth).mean() - 0.5 * np.mean(pair_crps)
    mean = flat.mean(axis=0)
    result = {
        "energy": float(energy),
        "crps": float(crps),
        "rmse": float(np.sqrt(np.mean((mean - truth) ** 2))),
        "mae": float(np.abs(mean - truth).mean()),
    }
    variogram = []
    weights = []
    for lag in (1, 2, 5, 10):
        if lag >= len(truth):
            continue
        observed = np.sqrt(np.abs(truth[lag:] - truth[:-lag]))
        predicted = np.sqrt(np.abs(flat[:, lag:] - flat[:, :-lag])).mean(axis=0)
        variogram.append(float(np.mean((observed - predicted) ** 2)))
        weights.append(1 / lag)
    result["variogram"] = float(np.average(variogram, weights=weights)) if weights else None
    # Monte Carlo error for dependent output: between-group batch estimates,
    # not an iid bootstrap over the correlated draws. Four groups give only
    # a coarse uncertainty diagnostic, which is recorded explicitly.
    group_distance = np.linalg.norm(chains - truth, axis=-1).mean(axis=1)
    result["distance_term_group_mcse"] = float(group_distance.std(ddof=1) / 2 / np.sqrt(len(truth)))
    pair_selection_mcse = 0.5 * np.sqrt(np.sum(pair_variance) / 36 / len(truth))
    group_crps = np.abs(chains - truth).mean(axis=(1, 2))
    leave_energy, leave_crps = [], []
    for omitted in range(4):
        keep = [i for i in range(4) if i != omitted]
        pair_keep = [i for i, pair in enumerate(pairs) if omitted not in pair]
        leave_energy.append(
            (group_distance[keep].mean() - 0.5 * np.mean(np.asarray(pair_energy)[pair_keep]))
            / np.sqrt(len(truth))
        )
        leave_crps.append(group_crps[keep].mean() - 0.5 * np.mean(np.asarray(pair_crps)[pair_keep]))

    def jackknife(values):
        return float(np.sqrt(0.75 * np.sum((values - np.mean(values)) ** 2)))

    chain_mcse = jackknife(np.array(leave_energy))
    result["energy_chain_mcse"] = chain_mcse
    result["crps_chain_mcse"] = jackknife(np.array(leave_crps))
    result["pair_selection_mcse"] = float(pair_selection_mcse)
    result["energy_mcse"] = float(np.hypot(chain_mcse, pair_selection_mcse))
    result["mcse_method"] = (
        "coarse four-group delete-one jackknife; conditional pair-selection SE separately reported"
    )
    for coverage in (0.5, 0.8, 0.95):
        lo, hi = np.quantile(flat, [(1 - coverage) / 2, (1 + coverage) / 2], axis=0)
        result[f"coverage_{coverage}"] = float(np.mean((truth >= lo) & (truth <= hi)))
        result[f"width_{coverage}"] = float(np.mean(hi - lo))
        result[f"coverage_by_position_{coverage}"] = ((truth >= lo) & (truth <= hi)).tolist()
    return result
