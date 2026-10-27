"""
Checks the gesture recordings in data/ for problems, and draws every
recording of each gesture on top of each other so you can see how
consistent you were.

Run:
    python check_data.py            report + plot window
    python check_data.py --no-show  report + saves reports/overview.png only
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

DATA_DIR = Path(__file__).parent / "data"
REPORT_DIR = Path(__file__).parent / "reports"

ACC_LIMIT = 7.9       # g: the IMU is set to +-8 g, so readings near this are clipped
GYR_LIMIT = 1000      # deg/s: set to +-1024 deg/s
MAX_GAP_MS = 25       # more than this between samples means samples were lost
MIN_PEAK_GYRO = 100   # deg/s: a real gesture rotates faster than this somewhere


def load(path):
    return np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)


def problems(rec):
    t, acc, gyr = rec[:, 0], rec[:, 1:4], rec[:, 4:7]
    found = []
    gaps = np.diff(t)
    if gaps.size and gaps.max() > MAX_GAP_MS:
        found.append(f"lost samples (gap of {gaps.max():.0f} ms)")
    if np.abs(acc).max() >= ACC_LIMIT:
        found.append("accel clipped at 8 g")
    if np.abs(gyr).max() >= GYR_LIMIT:
        found.append("gyro clipped at 1024 deg/s")
    if np.linalg.norm(gyr, axis=1).max() < MIN_PEAK_GYRO:
        found.append("barely moved")
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-show", action="store_true", help="don't open a window")
    args = ap.parse_args()

    labels = sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir()) if DATA_DIR.exists() else []
    if not labels:
        raise SystemExit("No recordings yet: run recorder.py first.")

    fig, axes = plt.subplots(len(labels), 3, figsize=(12, 2.6 * len(labels)), squeeze=False)
    total_bad = 0
    for row, label in enumerate(labels):
        files = sorted((DATA_DIR / label).glob("*.csv"))
        recs = [load(f) for f in files]
        durations = np.array([r[-1, 0] / 1000 for r in recs])
        rates = np.array([(len(r) - 1) / (r[-1, 0] / 1000) for r in recs if r[-1, 0] > 0])
        print(f"\n{label}: {len(recs)} recordings, {durations.mean():.2f} s average "
              f"({durations.min():.2f} to {durations.max():.2f} s), {rates.mean():.0f} Hz")

        median = np.median(durations)
        for f, r, d in zip(files, recs, durations):
            found = problems(r)
            if d < median / 2 or d > median * 2:
                found.append(f"{d:.2f} s is far from the usual {median:.2f} s")
            if found:
                total_bad += 1
                print(f"  ! {f.name}: " + "; ".join(found))

        # Overlay on a 0-1 time axis, so slow and fast versions line up roughly
        for r in recs:
            x = np.linspace(0, 1, len(r))
            for col in range(3):
                axes[row, col].plot(x, r[:, 4 + col], alpha=0.4, linewidth=1)
        for col, axis in enumerate("xyz"):
            axes[row, col].set_title(f"{label}: gyro {axis} (deg/s)", fontsize=9)
            axes[row, col].grid(alpha=0.3)

    print(f"\n{total_bad} recording(s) flagged." if total_bad else "\nNo problems found.")
    fig.tight_layout()
    REPORT_DIR.mkdir(exist_ok=True)
    out = REPORT_DIR / "overview.png"
    fig.savefig(out, dpi=90)
    print(f"Saved {out.relative_to(Path(__file__).parent)}")
    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
