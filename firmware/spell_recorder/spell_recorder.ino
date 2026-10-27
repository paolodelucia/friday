// =====================================================================
//  Spell recorder - Week 1 of Spells (see docs/spells.md)
//  Board: Waveshare ESP32-S3-Touch-AMOLED-1.8 (V2: CO5300 display)
//
//  Hold BOOT, make a gesture, release. While BOOT is held the board
//  streams the IMU (QMI8658, accel + gyro) over USB at 100 Hz:
//    BEGIN
//    S,<ms since BEGIN>,ax,ay,az,gx,gy,gz      accel in g, gyro in deg/s
//    END,<samples>,<ms>
//  spells/recorder.py on the laptop plots and saves each recording.
//
//  Arduino settings: same as friday_v0 (ESP32S3 Dev Module, USB CDC On
//  Boot Enabled, Flash 16MB, OPI PSRAM).
//  Libraries: SensorLib and Waveshare's arduino-v2 libraries.
// =====================================================================

#include <Wire.h>
#include "Arduino_GFX_Library.h"
#include "SensorQMI8658.hpp"
#include "pin_config.h"

const int      BUTTON    = 0;                  // BOOT
const int      SAMPLE_HZ = 100;
const uint32_t PERIOD_US = 1000000 / SAMPLE_HZ;
const uint32_t MAX_MS    = 10000;              // stop after 10 s (stuck button)

// Colours (RGB565)
const uint16_t C_BG     = 0x0000;
const uint16_t C_TEXT   = 0xFFFF;
const uint16_t C_DIM    = 0x8410;
const uint16_t C_ACCENT = 0x07FF;
const uint16_t C_REC    = 0xF800;

Arduino_DataBus* bus = new Arduino_ESP32QSPI(LCD_CS, LCD_SCLK, LCD_SDIO0, LCD_SDIO1, LCD_SDIO2, LCD_SDIO3);
Arduino_CO5300*  gfx = new Arduino_CO5300(bus, GFX_NOT_DEFINED, 0, LCD_WIDTH, LCD_HEIGHT, 16, 0, 0, 0);

SensorQMI8658 imu;
int recordings = 0;

// ---------------------------------------------------------------- display

void screen(const String& title, uint16_t color, const String& line1 = "", const String& line2 = "") {
  gfx->fillScreen(C_BG);
  gfx->setTextColor(color);
  gfx->setTextSize(4);
  gfx->setCursor(20, 40);
  gfx->print(title);
  gfx->setTextColor(C_DIM);
  gfx->setTextSize(2);
  gfx->setCursor(20, 100);
  gfx->print(line1);
  gfx->setCursor(20, 130);
  gfx->print(line2);
}

void idleScreen() {
  screen("Spells", C_ACCENT, "Hold BOOT and move,", "then release.");
  gfx->setTextColor(C_TEXT);
  gfx->setTextSize(2);
  gfx->setCursor(20, 190);
  gfx->print("Recordings: " + String(recordings));
}

// ---------------------------------------------------------------- IMU

bool imuInit() {
  // The QMI8658 answers on 0x6B or 0x6A depending on how the board wires it
  if (!imu.begin(Wire, QMI8658_L_SLAVE_ADDRESS, IIC_SDA, IIC_SCL) &&
      !imu.begin(Wire, QMI8658_H_SLAVE_ADDRESS, IIC_SDA, IIC_SCL)) {
    return false;
  }
  Wire.setClock(400000);
  // Sensor runs at ~224-250 Hz with a ~30 Hz low-pass; we sample it at 100 Hz.
  // 8 g and 1024 deg/s leave headroom for fast flicks and wrist twists.
  imu.configAccelerometer(SensorQMI8658::ACC_RANGE_8G, SensorQMI8658::ACC_ODR_250Hz, SensorQMI8658::LPF_MODE_3);
  imu.configGyroscope(SensorQMI8658::GYR_RANGE_1024DPS, SensorQMI8658::GYR_ODR_224_2Hz, SensorQMI8658::LPF_MODE_3);
  imu.enableAccelerometer();
  imu.enableGyroscope();
  return true;
}

// Streams samples while BOOT is held. Returns the number of samples sent.
int recordWhileHeld() {
  Serial.println("BEGIN");
  float ax = 0, ay = 0, az = 0, gx = 0, gy = 0, gz = 0;
  int n = 0;
  uint32_t start = micros();
  uint32_t next = start;
  while (digitalRead(BUTTON) == LOW && (micros() - start) / 1000 < MAX_MS) {
    while ((int32_t)(micros() - next) < 0) {}     // wait for the next 10 ms tick
    next += PERIOD_US;
    imu.getAccelerometer(ax, ay, az);
    imu.getGyroscope(gx, gy, gz);
    Serial.printf("S,%lu,%.3f,%.3f,%.3f,%.1f,%.1f,%.1f\n",
                  (unsigned long)((micros() - start) / 1000), ax, ay, az, gx, gy, gz);
    n++;
  }
  Serial.printf("END,%d,%lu\n", n, (unsigned long)((micros() - start) / 1000));
  return n;
}

// ---------------------------------------------------------------- main

void setup() {
  Serial.setTxBufferSize(4096);    // a recording is ~6 KB/s; don't stall on bursts
  Serial.begin(115200);
  pinMode(BUTTON, INPUT_PULLUP);

  gfx->begin();
  gfx->setBrightness(200);
  screen("Spells", C_ACCENT, "starting up");

  if (!imuInit()) {
    screen("IMU failed", C_REC, "QMI8658 not found", "on 0x6B or 0x6A");
    while (true) {
      Serial.println("# IMU not found");
      delay(1000);
    }
  }
  Serial.println("# spell_recorder ready");
  idleScreen();
}

void loop() {
  if (digitalRead(BUTTON) == LOW) {
    screen("Recording", C_REC, "release BOOT to stop");
    int n = recordWhileHeld();
    recordings++;
    screen("Got it", C_ACCENT, String(n) + " samples, " + String(n / (float)SAMPLE_HZ, 1) + " s");
    while (digitalRead(BUTTON) == LOW) delay(10);
    delay(600);
    idleScreen();
  }
  delay(5);
}
