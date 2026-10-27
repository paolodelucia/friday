"""
Answers "is one example enough?" using your recordings in data/.

It pretends to teach each spell from ONE random recording, then tries to
recognise every other recording, and repeats that many times with different
picks. It also points out recordings that don't look like the rest of their
gesture (a different start point, a different direction, a bad take).

Run:
    python evaluate.py            report + distance picture window
    python evaluate.py --no-show  report + saves reports/distances.png only
"""

import argparse
import itertools
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from check_data import DATA_DIR, REPORT_DIR, load
from matcher import dtw_distance, preprocess

TRIALS = 1000
OUTLIER_FACTOR = 1.6   # a recording this much further from its own gesture than usual is odd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-show", action="store_true", help="don't open a window")
    args = ap.parse_args()

    names, labels, feats = [], [], []
    for folder in sorted(p for p in DATA_DIR.iterdir() if p.is_dir()):
        for f in sorted(folder.glob("*.csv")):
            names.append(f.name)
            labels.append(folder.name)
            feats.append(preprocess(load(f)))
    labels = np.array(labels)
    classes = sorted(set(labels))
    n = len(feats)
    if len(classes) < 2:
        raise SystemExit("Record at least two different gestures first.")
    print(f"{n} recordings of {len(classes)} gestures: " +
          ", ".join(f"{c} ({(labels == c).sum()})" for c in classes))

    print(f"Comparing every pair ({n * (n - 1) // 2} DTW runs)...")
    dist = np.zeros((n, n))
    for i, j in itertools.combinations(range(n), 2):
        dist[i, j] = dist[j, i] = dtw_distance(feats[i], feats[j])

    # 1. One-shot: teach each spell from one random recording, test on the rest
    rng = np.random.default_rng(0)
    idx = {c: np.flatnonzero(labels == c) for c in classes}
    correct = {c: 0 for c in classes}
    tested = {c: 0 for c in classes}
    margins = []
    for _ in range(TRIALS):
        templates = {c: rng.choice(idx[c]) for c in classes}
        tmpl_idx = list(templates.values())
        for q in range(n):
            if q in tmpl_idx:
                continue
            d = {c: dist[q, t] for c, t in templates.items()}
            own = d[labels[q]]
            nearest_other = min(v for c, v in d.items() if c != labels[q])
            tested[labels[q]] += 1
            correct[labels[q]] += own < nearest_other
            margins.append(nearest_other / own)
    margins = np.array(margins)

    print(f"\nOne example per spell, {TRIALS} random picks:")
    for c in classes:
        print(f"  {c:10s} recognised {100 * correct[c] / tested[c]:5.1f}% of the time")
    total = 100 * sum(correct.values()) / sum(tested.values())
    print(f"  overall    {total:5.1f}%")
    print(f"\nSafety margin (nearest wrong spell / right spell; above 1 = correct):")
    print(f"  typical {np.median(margins):.2f}x,  worst 5% {np.percentile(margins, 5):.2f}x,  "
          f"worst {margins.min():.2f}x")

    # 2. Odd recordings: far from the rest of their own gesture
    print("\nRecordings that don't look like the rest of their gesture:")
    odd = 0
    for c in classes:
        members = idx[c]
        typical = np.array([np.median(dist[i, members[members != i]]) for i in members])
        for i, t in zip(members, typical):
            if t > OUTLIER_FACTOR * np.median(typical):
                odd += 1
                print(f"  {c}/{names[i]}: {t / np.median(typical):.1f}x further than usual")
    if not odd:
        print("  none")

    # 3. Picture: dark blocks on the diagonal = each gesture is self-consistent
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(dist, cmap="viridis")
    edges = np.cumsum([len(idx[c]) for c in classes])[:-1] - 0.5
    for e in edges:
        ax.axhline(e, color="white", linewidth=1)
        ax.axvline(e, color="white", linewidth=1)
    centers = np.cumsum([0] + [len(idx[c]) for c in classes])
    ticks = [(centers[k] + centers[k + 1] - 1) / 2 for k in range(len(classes))]
    ax.set_xticks(ticks, classes)
    ax.set_yticks(ticks, classes)
    ax.set_title("DTW distance between recordings (darker = more alike)")
    fig.colorbar(im)
    fig.tight_layout()
    REPORT_DIR.mkdir(exist_ok=True)
    out = REPORT_DIR / "distances.png"
    fig.savefig(out, dpi=90)
    print(f"\nSaved {out.relative_to(Path(__file__).parent)}")
    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
