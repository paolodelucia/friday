"""
The spell matcher: compares two gesture recordings with DTW (dynamic time
warping), which lines up the two motions even if one was done faster or
slower, then measures how different they are. Smaller distance = more alike.

This is the Python version, where it's quick to experiment. The board will
run the same steps in C.
"""

import numpy as np

QUIET_DPS = 40     # deg/s: slower than this at the start or end is just holding still
GYRO_SCALE = 200   # deg/s that counts as "1" when mixing gyro and accel
ACC_WEIGHT = 0.5   # how much accel counts next to gyro (gyro is more reliable)
BAND = 0.3         # DTW may stretch time by up to 30% of the gesture's length


def preprocess(rec):
    """Raw recording (t_ms, ax, ay, az, gx, gy, gz) -> feature frames at 50 Hz."""
    acc, gyr = rec[:, 1:4], rec[:, 4:7]
    # Trim the still parts before and after the motion (pressing and releasing BOOT)
    moving = np.flatnonzero(np.linalg.norm(gyr, axis=1) > QUIET_DPS)
    if moving.size >= 10:
        acc, gyr = acc[moving[0]:moving[-1] + 1], gyr[moving[0]:moving[-1] + 1]
    # Removing the average accel drops gravity, so how the board is tilted matters less
    feats = np.hstack([gyr / GYRO_SCALE, (acc - acc.mean(axis=0)) * ACC_WEIGHT])
    # 100 Hz -> 50 Hz: average pairs of samples (4x less DTW work, same shape)
    n = len(feats) // 2 * 2
    return feats[:n].reshape(-1, 2, feats.shape[1]).mean(axis=1)


def dtw_distance(a, b):
    """DTW distance between two feature sequences, averaged over the path length."""
    n, m = len(a), len(b)
    cost = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    band = max(int(BAND * max(n, m)), abs(n - m) + 1)
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0
    for i in range(1, n + 1):
        lo, hi = max(1, i - band), min(m, i + band)
        for j in range(lo, hi + 1):
            D[i, j] = cost[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return D[n, m] / (n + m)
