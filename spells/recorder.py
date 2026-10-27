"""
Records gestures from the board (firmware/spell_recorder) and saves them,
so we can build and test the spell matcher. Each recording is plotted live:
accelerometer on top, gyroscope below.

Run (board plugged in over USB):
    python recorder.py zed              every recording is saved as a "zed"
    python recorder.py zed --port COM7  if the board isn't found by itself

Hold BOOT on the board, make the gesture, release. Repeat.
In the plot window, press d to delete the last saved recording.
Recordings go to data/<label>/<label>_001.csv, _002.csv, ...
"""

import argparse
import csv
import re
import sys
import threading
from pathlib import Path

import matplotlib.pyplot as plt
import serial
from serial.tools import list_ports

ESPRESSIF_VID = 0x303A   # the S3's native USB shows up with this vendor ID
MIN_SAMPLES = 20         # under 0.2 s: a tap on BOOT, not a gesture
FIELDS = ["t_ms", "ax", "ay", "az", "gx", "gy", "gz"]
DATA_DIR = Path(__file__).parent / "data"


class Recordings:
    """Turns the board's BEGIN / S,... / END lines into finished recordings."""

    def __init__(self):
        self.lock = threading.Lock()
        self.current = []     # samples of the recording in progress, or the last one
        self.recording = False
        self.finished = []    # complete recordings waiting to be saved

    def feed(self, line):
        line = line.strip()
        with self.lock:
            if line == "BEGIN":
                self.current = []
                self.recording = True
            elif line.startswith("S,") and self.recording:
                parts = line.split(",")[1:]
                if len(parts) == len(FIELDS):
                    try:
                        self.current.append([float(p) for p in parts])
                    except ValueError:
                        pass  # a line garbled in transit: skip it
            elif line.startswith("END") and self.recording:
                self.recording = False
                self.finished.append(list(self.current))
            elif line.startswith("#"):
                print("board:", line[1:].strip())

    def snapshot(self):
        with self.lock:
            return list(self.current), self.recording

    def take_finished(self):
        with self.lock:
            done, self.finished = self.finished, []
            return done


def find_port():
    ports = list(list_ports.comports())
    for p in ports:
        if p.vid == ESPRESSIF_VID:
            return p.device
    print("Couldn't find the board. Ports I can see:")
    for p in ports:
        print(f"  {p.device}  {p.description}")
    sys.exit("Plug the board in (and close Arduino's Serial Monitor), or pass --port COMx")


def read_serial(port, recs, lost):
    try:
        with serial.Serial(port, 115200, timeout=1) as ser:
            while True:
                raw = ser.readline()
                if raw:
                    recs.feed(raw.decode(errors="replace"))
    except serial.SerialException as e:
        print(f"Lost the board: {e}")
        lost.set()


def save(label, samples):
    folder = DATA_DIR / label
    folder.mkdir(parents=True, exist_ok=True)
    taken = [int(m.group(1)) for f in folder.glob(f"{label}_*.csv")
             if (m := re.fullmatch(rf"{re.escape(label)}_(\d+)\.csv", f.name))]
    path = folder / f"{label}_{max(taken, default=0) + 1:03d}.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for s in samples:
            w.writerow([int(s[0])] + s[1:])
    return path


def describe(samples):
    ms = samples[-1][0] - samples[0][0]
    rate = (len(samples) - 1) / (ms / 1000) if ms else 0
    return f"{len(samples)} samples, {ms / 1000:.2f} s, {rate:.0f} Hz"


def main():
    ap = argparse.ArgumentParser(description="Record gestures for Friday spells.")
    ap.add_argument("label", help="name of the gesture you're recording, e.g. zed")
    ap.add_argument("--port", help="serial port, e.g. COM7 (found automatically if left out)")
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        sys.exit("Use only letters, numbers, - and _ in the label.")

    port = args.port or find_port()
    print(f"Listening on {port}. Hold BOOT, move, release. Close the plot window to stop.")
    recs = Recordings()
    lost = threading.Event()
    threading.Thread(target=read_serial, args=(port, recs, lost), daemon=True).start()

    fig, (acc_ax, gyr_ax) = plt.subplots(2, 1, sharex=True, figsize=(9, 6))
    acc_lines = [acc_ax.plot([], [], label=a)[0] for a in "xyz"]
    gyr_lines = [gyr_ax.plot([], [], label=a)[0] for a in "xyz"]
    acc_ax.set_ylabel("accel (g)")
    gyr_ax.set_ylabel("gyro (deg/s)")
    gyr_ax.set_xlabel("time (s)")
    for ax in (acc_ax, gyr_ax):
        ax.legend(loc="upper right")
        ax.grid(alpha=0.3)

    saved = []   # paths saved in this session, newest last, so d can undo
    status = {"text": "waiting for a recording"}

    def on_key(event):
        if event.key == "d" and saved:
            path = saved.pop()
            path.unlink(missing_ok=True)
            print(f"deleted {path.relative_to(DATA_DIR.parent)}")
            status["text"] = f"deleted {path.name}"

    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show(block=False)

    drawn = None
    while plt.fignum_exists(fig.number) and not lost.is_set():
        for rec in recs.take_finished():
            if len(rec) < MIN_SAMPLES:
                print(f"ignored a {len(rec)}-sample tap")
                continue
            path = save(args.label, rec)
            saved.append(path)
            print(f"saved {path.relative_to(DATA_DIR.parent)}  ({describe(rec)})")
            status["text"] = f"saved {path.name}: {describe(rec)}"

        samples, live = recs.snapshot()
        title = f"{args.label}: " + ("recording..." if live else status["text"]) + "   (d = delete last)"
        if (len(samples), title) != drawn:
            t = [s[0] / 1000 for s in samples]
            for i, line in enumerate(acc_lines):
                line.set_data(t, [s[1 + i] for s in samples])
            for i, line in enumerate(gyr_lines):
                line.set_data(t, [s[4 + i] for s in samples])
            for ax in (acc_ax, gyr_ax):
                ax.relim()
                ax.autoscale_view()
            fig.suptitle(title)
            fig.canvas.draw_idle()
            drawn = (len(samples), title)
        plt.pause(0.05)


if __name__ == "__main__":
    main()
