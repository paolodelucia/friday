// =====================================================================
//  Friday v0 - the voice loop
//  Board: Waveshare ESP32-S3-Touch-AMOLED-1.8 (V2: CO5300 display)
//
//  Hold the BOOT button, speak, release.
//  The board sends your voice to the Friday server on your PC, which
//  transcribes it (Whisper), asks Claude, and sends back speech (Piper).
//
//  Arduino settings (Tools menu):
//    Board: ESP32S3 Dev Module     USB CDC On Boot: Enabled
//    Flash Size: 16MB              PSRAM: OPI PSRAM
//    Partition Scheme: 16M Flash (3MB APP/9.9MB FATFS)
//  Libraries: the ones from Waveshare's arduino-v2/libraries folder
//  (already installed if the examples worked).
// =====================================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include "ESP_I2S.h"
#include "Arduino_GFX_Library.h"
#include "pin_config.h"
#include "es8311.h"

// Known networks. Friday scans, joins the strongest one it recognizes,
// and talks to that network's server address. The list lives in
// secrets.h (not committed): copy secrets.example.h to secrets.h and edit it.
struct KnownNetwork { const char* ssid; const char* pass; const char* server; };
#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "secrets.h is missing: copy secrets.example.h to secrets.h and fill in your Wi-Fi"
#endif
const int NUM_NETWORKS = sizeof(NETWORKS) / sizeof(NETWORKS[0]);
String serverUrl;   // filled in when a network is joined

const int   SAMPLE_RATE  = 16000;
const int   MAX_SECONDS  = 10;
const int   TALK_BUTTON  = 0;    // BOOT button
const int   VOLUME       = 85;   // speaker 0-100
const es8311_mic_gain_t MIC_GAIN = (es8311_mic_gain_t)3;  // 0-7

// Colours (RGB565)
const uint16_t C_BG    = 0x0000;
const uint16_t C_TEXT  = 0xFFFF;
const uint16_t C_DIM   = 0x8410;
const uint16_t C_ACCENT= 0x07FF;
const uint16_t C_REC   = 0xF800;
const uint16_t C_THINK = 0xFFE0;

I2SClass i2s;
Arduino_DataBus* bus = new Arduino_ESP32QSPI(LCD_CS, LCD_SCLK, LCD_SDIO0, LCD_SDIO1, LCD_SDIO2, LCD_SDIO3);
Arduino_CO5300*  gfx = new Arduino_CO5300(bus, GFX_NOT_DEFINED, 0, LCD_WIDTH, LCD_HEIGHT, 16, 0, 0, 0);

uint8_t* recBuf = nullptr;                                  // stereo recording, in PSRAM
const size_t REC_BUF_BYTES = (size_t)SAMPLE_RATE * 4 * MAX_SECONDS;  // 16-bit x 2 channels

// ---------------------------------------------------------------- display

void drawWrapped(const String& s, int x, int& y, int size, uint16_t color) {
  gfx->setTextSize(size);
  gfx->setTextColor(color);
  const int maxChars = (LCD_WIDTH - 2 * x) / (6 * size);
  const int lineH = 8 * size + 6;
  String line, word;
  String text = s + " ";
  for (size_t i = 0; i < text.length(); i++) {
    char c = text[i];
    if (c == ' ' || c == '\n') {
      int needed = line.length() + word.length() + (line.length() ? 1 : 0);
      if (needed > maxChars && line.length()) {
        gfx->setCursor(x, y); gfx->print(line);
        y += lineH; line = word;
      } else {
        if (line.length()) line += " ";
        line += word;
      }
      word = "";
      if (c == '\n') { gfx->setCursor(x, y); gfx->print(line); y += lineH; line = ""; }
      if (y > LCD_HEIGHT - lineH) return;   // out of room
    } else {
      word += c;
    }
  }
  if (line.length()) { gfx->setCursor(x, y); gfx->print(line); y += lineH; }
}

void screen(const String& title, uint16_t color, const String& sub = "") {
  gfx->fillScreen(C_BG);
  int y = 40;
  drawWrapped(title, 20, y, 4, color);
  if (sub.length()) { y += 10; drawWrapped(sub, 20, y, 2, C_DIM); }
}

// ---------------------------------------------------------------- audio

esp_err_t codecInit() {
  es8311_handle_t es = es8311_create(0, ES8311_ADDRRES_0);
  if (!es) return ESP_FAIL;
  const es8311_clock_config_t clk = {
    .mclk_inverted = false, .sclk_inverted = false, .mclk_from_mclk_pin = true,
    .mclk_frequency = SAMPLE_RATE * 256, .sample_frequency = SAMPLE_RATE
  };
  ESP_ERROR_CHECK(es8311_init(es, &clk, ES8311_RESOLUTION_16, ES8311_RESOLUTION_16));
  es8311_sample_frequency_config(es, clk.mclk_frequency, clk.sample_frequency);
  es8311_microphone_config(es, false);
  es8311_voice_volume_set(es, VOLUME, NULL);
  es8311_microphone_gain_set(es, MIC_GAIN);
  return ESP_OK;
}

// Records while the button is held. Returns mono byte count (written into recBuf).
size_t recordWhileHeld() {
  // drop stale audio sitting in the I2S buffers
  uint8_t junk[1024];
  for (int i = 0; i < 4; i++) i2s.readBytes((char*)junk, sizeof(junk));

  size_t pos = 0;
  while (digitalRead(TALK_BUTTON) == LOW && pos + 1024 <= REC_BUF_BYTES) {
    pos += i2s.readBytes((char*)recBuf + pos, 1024);
  }
  pos &= ~3;  // whole stereo frames

  // The codec's mic lands on one channel; keep the louder one as mono.
  int16_t* s = (int16_t*)recBuf;
  size_t frames = pos / 4;
  uint64_t eL = 0, eR = 0;
  for (size_t i = 0; i < frames; i++) { eL += abs(s[2*i]); eR += abs(s[2*i+1]); }
  int ch = (eR > eL) ? 1 : 0;
  for (size_t i = 0; i < frames; i++) s[i] = s[2*i + ch];   // in place, safe
  return frames * 2;
}

void writeSilence(int ms) {
  static uint8_t zeros[1024] = {0};
  int chunks = (SAMPLE_RATE * 4 * ms / 1000) / sizeof(zeros) + 1;
  for (int i = 0; i < chunks; i++) i2s.write(zeros, sizeof(zeros));
}

// Streams mono 16 kHz PCM from the server and plays it.
void playFromServer(const String& audioId) {
  HTTPClient http;
  http.begin(serverUrl + "/audio/" + audioId);
  http.setTimeout(30000);
  if (http.GET() != 200) { http.end(); return; }

  WiFiClient* stream = http.getStreamPtr();
  int remaining = http.getSize();          // -1 if unknown
  static uint8_t in[1024];
  static int16_t out[1024];                // stereo = 2x samples
  unsigned long lastData = millis();

  while (http.connected() && (remaining > 0 || remaining == -1)) {
    size_t avail = stream->available();
    if (avail >= 2) {
      size_t n = stream->readBytes(in, min(avail, sizeof(in)) & ~1);
      int16_t* mono = (int16_t*)in;
      for (size_t i = 0; i < n / 2; i++) { out[2*i] = mono[i]; out[2*i+1] = mono[i]; }
      i2s.write((uint8_t*)out, n * 2);
      if (remaining > 0) remaining -= n;
      lastData = millis();
    } else {
      if (millis() - lastData > 5000) break;   // stalled
      delay(2);
    }
  }
  writeSilence(150);
  http.end();
}

// ---------------------------------------------------------------- network

// Scans, picks the strongest known network, joins it, sets serverUrl.
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED && serverUrl.length()) return;

  screen("Wi-Fi...", C_DIM, "scanning");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);           // forget the last network (you may have moved)
  delay(100);
  int found = WiFi.scanNetworks();

  int best = -1, bestRssi = -1000;
  for (int i = 0; i < found; i++) {
    for (int k = 0; k < NUM_NETWORKS; k++) {
      if (WiFi.SSID(i) == NETWORKS[k].ssid && WiFi.RSSI(i) > bestRssi) {
        best = k; bestRssi = WiFi.RSSI(i);
      }
    }
  }

  if (best < 0) {                  // nothing we know: show what we can see
    String seen;
    for (int i = 0; i < found && i < 5; i++) seen += WiFi.SSID(i) + "\n";
    WiFi.scanDelete();
    screen("No known Wi-Fi", C_REC, found ? "I see:\n" + seen : "No networks found");
    serverUrl = "";
    return;
  }
  WiFi.scanDelete();

  screen("Wi-Fi...", C_DIM, NETWORKS[best].ssid);
  WiFi.begin(NETWORKS[best].ssid, NETWORKS[best].pass);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 15000) delay(250);

  if (WiFi.status() == WL_CONNECTED) {
    serverUrl = NETWORKS[best].server;
  } else {
    serverUrl = "";
    screen("Wi-Fi failed", C_REC, String(NETWORKS[best].ssid) + "\nwrong password?");
  }
}

// Sends audio, shows the reply, plays the speech.
void talkToServer(size_t monoBytes) {
  connectWiFi();
  if (WiFi.status() != WL_CONNECTED || !serverUrl.length()) return;   // error already on screen

  screen("Thinking...", C_THINK);
  HTTPClient http;
  http.begin(serverUrl + "/talk");
  http.setTimeout(60000);
  http.addHeader("Content-Type", "application/octet-stream");
  const char* keys[] = {"X-Audio-Id"};
  http.collectHeaders(keys, 1);

  int code = http.POST(recBuf, monoBytes);
  if (code != 200) {
    screen("Server error", C_REC, code < 0 ? "Can't reach " + serverUrl + " - is server.py running?"
                                           : "HTTP " + String(code));
    http.end();
    return;
  }
  String body = http.getString();     // line 1: what you said, rest: reply
  String audioId = http.header("X-Audio-Id");
  http.end();

  int nl = body.indexOf('\n');
  String you   = nl >= 0 ? body.substring(0, nl) : "";
  String reply = nl >= 0 ? body.substring(nl + 1) : body;

  gfx->fillScreen(C_BG);
  int y = 24;
  if (you.length()) { drawWrapped("> " + you, 16, y, 2, C_DIM); y += 12; }
  drawWrapped(reply, 16, y, 3, C_TEXT);

  if (audioId.length()) playFromServer(audioId);
}

// ---------------------------------------------------------------- main

// Idle screen; keeps any Wi-Fi error visible instead of hiding it.
void idleScreen() {
  if (WiFi.status() == WL_CONNECTED && serverUrl.length())
    screen("Friday", C_ACCENT, "Hold BOOT and talk\n\non " + WiFi.SSID());
}

void setup() {
  Serial.begin(115200);
  pinMode(TALK_BUTTON, INPUT_PULLUP);

  gfx->begin();
  gfx->setBrightness(200);
  screen("Friday", C_ACCENT, "starting up");

  recBuf = (uint8_t*)ps_malloc(REC_BUF_BYTES);
  if (!recBuf) { screen("No PSRAM", C_REC, "Tools > PSRAM > OPI PSRAM"); while (true) delay(1000); }

  pinMode(PA, OUTPUT);
  digitalWrite(PA, HIGH);               // speaker amplifier on
  i2s.setPins(I2S_BCK_IO, I2S_WS_IO, I2S_DO_IO, I2S_DI_IO, I2S_MCK_IO);
  if (!i2s.begin(I2S_MODE_STD, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO, I2S_STD_SLOT_BOTH)) {
    screen("Audio failed", C_REC, "I2S init");
    while (true) delay(1000);
  }
  Wire.begin(IIC_SDA, IIC_SCL);
  if (codecInit() != ESP_OK) screen("Codec failed", C_REC);

  connectWiFi();
  idleScreen();
}

void loop() {
  if (digitalRead(TALK_BUTTON) == LOW) {
    screen("Listening", C_REC, "release to send");
    size_t bytes = recordWhileHeld();
    if (bytes < SAMPLE_RATE / 2) {                   // under 0.25 s: ignore taps
      connectWiFi();   // a tap also retries Wi-Fi (e.g. after you move rooms)
      if (WiFi.status() == WL_CONNECTED && serverUrl.length()) idleScreen();
      return;
    }
    talkToServer(bytes);
    // wait for the button to be free before listening again
    while (digitalRead(TALK_BUTTON) == LOW) delay(10);
  }
  delay(10);
}
