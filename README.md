# Friday

A pocket voice assistant: hold a button, speak, and get Claude's answer spoken
back and shown on a 1.8" AMOLED screen. The goal is a device you can carry instead
of your phone for parts of the day.

```
Friday (ESP32-S3)  --raw audio-->  server.py  -->  Whisper  -->  Claude  -->  Piper
Friday             <--text + speech----------------------------------------'
```

The device records, plays audio and shows text. Everything smart runs on the
server, so it can improve without reflashing the board.

**Status:** v0 works. Press, talk, and the answer comes back in about 2 seconds.

## Hardware

- [Waveshare ESP32-S3-Touch-AMOLED-1.8](https://www.waveshare.com/esp32-s3-touch-amoled-1.8.htm),
  **V2** (CO5300 display, CST820 touch, ES8311 audio codec, mic and speaker)
- USB-C cable. A battery is optional for now: 3.7V LiPo with an MX1.25 plug, max 3.85 x 24 x 28 mm.

## Repo layout

| Path | What |
|---|---|
| `firmware/friday_v0/` | Arduino sketch for the board (the `es8311` files are Espressif's codec driver, Apache-2.0) |
| `server/` | Python server: Whisper, Claude, Piper |
| `experiments/` | First ESP32 sketches: blink test and a Bluetooth "ghost keyboard" |

## Setup

### Server (Windows)

Use **Python 3.12**. Some dependencies don't support 3.14 yet.

```bat
cd server
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m piper.download_voices en_US-lessac-medium
setx ANTHROPIC_API_KEY "sk-ant-..."
```

Create the API key **inside a workspace** (Console > Settings > Workspaces). An
organization-level key fails with "not scoped to a workspace". Alternatively, set
`FRIDAY_WORKSPACE` to the workspace ID.

Open a **new** terminal (so it picks up the key), activate the venv, and run:

```bat
set FRIDAY_MODEL=claude-sonnet-5-5
python server.py
```

It prints the address to put in the firmware. Test without the board:
`python test_talk.py "What is the capital of Italy?"`, which saves `reply.wav`.

### Firmware

1. Install Waveshare's Arduino libraries from their repo (`examples/arduino-v2/libraries`).
2. In `firmware/friday_v0/`, copy `secrets.example.h` to `secrets.h` and fill in your
   networks: one `{ ssid, password, server }` line each. Friday joins the strongest one
   it knows. `secrets.h` is git-ignored, so your passwords stay out of the repo.
   The board needs 2.4 GHz Wi-Fi on the same network as the server.
3. Tools: **ESP32S3 Dev Module**, USB CDC On Boot **Enabled**, Flash **16MB**,
   PSRAM **OPI PSRAM**, Partition **16M Flash (3MB APP/9.9MB FATFS)**.
4. Upload, then unplug and replug the board.

Hold **BOOT**, speak, release.

## Settings

| Setting | Where | Default |
|---|---|---|
| Claude model | `FRIDAY_MODEL` env var | `claude-haiku-5-5` |
| Whisper model | `FRIDAY_WHISPER` env var | `base.en` (`small.en` is more accurate) |
| Personality | `SYSTEM_PROMPT` in `server.py` | short, spoken answers |
| Volume / mic gain | `VOLUME`, `MIC_GAIN` in the sketch | 85 / 3 |
| Max recording | `MAX_SECONDS` in the sketch | 10 s |

## Roadmap

- **v1, useful:** note and to-do capture, a morning brief (Gmail and calendar),
  weather and transit, streaming replies for speed.
- **v1.5, pocketable:** raise-to-wake (IMU), deep sleep, battery, a nicer screen
  user interface, and two ESP32 helper nodes (desk light and keyboard handoff, room
  presence that triggers the morning brief).
- **v2, phone-free:** server on a cloud VM, eduroam, an offline queue on the SD
  card, an errand relay with confirmation.
- **Later:** wake word, cellular, custom case.
