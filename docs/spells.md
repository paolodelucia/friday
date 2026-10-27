# Spells: teach Friday a gesture in 5 seconds

Make any motion with Friday once, say what it means ("this means text Alex I'm
running late"), and from then on that motion does it. No app, no training session,
no menus. The model learns your gesture on the chip from a single example.

**The clip (15 s):** draw a Z in the air and the laptop's music stops instantly.
"Watch, I'll make a new one": twist the wrist, say "this means text Alex I'm on my
way". Five seconds later, twist again, and Alex's phone buzzes on camera.

## How it works

```
QMI8658 IMU (100 Hz, accel + gyro)
   |
   v
Segment: hold BOOT while moving (v1)  ->  motion-triggered, no button (v3)
   |
   v
Match against stored spells: DTW nearest neighbour (v1)  ->  learned embedding (v2)
   |          plus a rejection threshold, so random motion casts nothing
   v
Cast: local action (BLE keyboard to the laptop)  or  agent action (server + Claude)
```

**Teach:** hold BOOT, do the motion (1 to 3 times), release, say what it means. The
server asks Claude to turn the sentence into an action spec, the screen shows it, and
the template plus the action are saved to flash.

**Cast:** do the motion. The screen draws the trail and the spell's name, then runs
the action. Anything that sends, spends or deletes shows on screen and waits for a
spoken "confirm" (the Friday rule).

## Milestones

### Week 1 (Oct 26 to Nov 1): see and match gestures
Gestures are silent, so all of this works in the library.
- [ ] Firmware: read the QMI8658 at 100 Hz; hold BOOT to record; stream samples to
      the laptop (Serial first, Wi-Fi later).
- [ ] Python: a recorder and live plot; save labelled recordings to `data/`.
- [ ] Python: a DTW matcher. Measure accuracy with one example per spell, for 5
      spells, using your own recordings. Iterate here, where it's fast.
- [ ] Firmware: port DTW to the board. Teach 3 spells with BOOT, cast them, and the
      screen shows which one matched.
- **Done when:** 5 spells taught from one example each, at least 90% recognised.

### Week 2 (Nov 2 to Nov 8): spells do things
- [ ] Voice teaching: after recording, speak the meaning. The server turns it into
      an action spec with Claude, and the screen asks you to confirm.
- [ ] Storage: spells survive a reboot (NVS or the SD card).
- [ ] Local actions over BLE keyboard (from `experiments/ghost_keyboard`): play or
      pause, next track, lock the PC, type text.
- [ ] Agent actions through the server: send a message (Telegram or Discord bot:
      free and quick to set up), add a reminder, ask Claude something and show it.
- [ ] Rejection: record 10 minutes of normal movement (walking, typing, picking it
      up) and tune the threshold until it casts nothing.
- **Done when:** a taught spell sends a real message, and normal movement casts
  nothing.

### Week 3 (Nov 9 to Nov 14): make it feel like magic
- [ ] Draw the gesture's trail on the AMOLED as you move (integrate the gyro).
- [ ] Cast animation and sound.
- [ ] Optional: motion-triggered segmentation, so casting needs no button.
- [ ] Demo script, rehearsal, and the clip. **Queen's Playground hackathon, Nov 14.**

### After the hackathon: the embedded ML version
- [ ] Train a small 1D-CNN embedding model offline (your recordings plus public IMU
      gesture datasets), using metric learning, so similar gestures land close.
- [ ] Quantize to int8; run it with ESP-DL or TFLite Micro on the S3. A new spell is
      then one embedding of one example, compared by distance.
- [ ] Benchmark it against DTW: accuracy, false casts per hour, latency, power.
      That comparison is the write-up for a résumé or a post.
- [ ] Hardware: design a wearable (a ring or a bracelet) in KiCad, with its own
      battery. It also becomes the input method for the Friday phone.

## Risks

| Risk | Plan |
|---|---|
| Random movement casts spells | Hold BOOT to arm (v1); a rejection threshold tuned on negatives; later, raise to arm |
| The same gesture held at a different angle doesn't match | Lean on the gyro (it's independent of orientation); remove gravity from accel; allow 1 to 3 examples |
| The gesture varies from day to day | DTW tolerates speed changes; re-test on recordings from different days |
| A spoken "confirm" kills the silent magic | Only send/spend/delete spells need it; see the open question below |
| No battery yet | Run on USB or a power bank for the demo; the battery comes with the custom hardware |

## Open questions for Paolo

1. **Form for the demo:** worn on the wrist like a watch, or held like a wand?
2. **Confirm gesture:** should a dedicated "confirm" gesture count as confirmation,
   instead of saying "confirm"? It would change the Friday rule, so it's your call.
3. **Messaging for the demo:** Telegram, Discord, or something else?
