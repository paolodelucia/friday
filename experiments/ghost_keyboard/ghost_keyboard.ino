// Step 2: Bluetooth "Ghost Keyboard"
// The ESP32 pretends to be a Bluetooth keyboard.
//   - Short press BOOT button  -> play/pause music
//   - Long press (hold ~1s)    -> types a message
// Blue LED = solid when connected, blinking when waiting to pair.
//
// Library: "ESP32 BLE Keyboard" by T-vK
//   Install: download ZIP from github.com/T-vK/ESP32-BLE-Keyboard
//   then Sketch > Include Library > Add .ZIP Library
// Board: "ESP32 Dev Module"
//
// esp32 core 3.x: if compile fails with a std::string / String error, edit
//   libraries/ESP32-BLE-Keyboard/BleKeyboard.cpp:
//     BLEDevice::init(deviceName)  ->  BLEDevice::init(String(deviceName.c_str()))
//     ...setValue(deviceManufacturer)  ->  ...setValue(String(deviceManufacturer.c_str()))

#include <BleKeyboard.h>

BleKeyboard bleKeyboard("Ghost Keyboard", "Paolo", 100);

const int BUTTON = 0;   // BOOT button on the board
const int LED = 2;      // onboard blue LED
const unsigned long LONG_PRESS_MS = 800;

const char* MESSAGE = "hello from the ghost keyboard :)";

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON, INPUT_PULLUP);
  pinMode(LED, OUTPUT);
  bleKeyboard.begin();
  Serial.println("Ghost Keyboard ready. Pair 'Ghost Keyboard' in your Bluetooth settings.");
}

void loop() {
  if (!bleKeyboard.isConnected()) {
    // Blink while waiting to pair
    digitalWrite(LED, (millis() / 400) % 2);
    return;
  }

  digitalWrite(LED, HIGH);  // solid = connected

  if (digitalRead(BUTTON) == LOW) {          // button pressed
    unsigned long start = millis();
    while (digitalRead(BUTTON) == LOW) {     // wait for release
      delay(10);
    }
    unsigned long held = millis() - start;

    if (held < 30) return;                   // ignore bounce

    if (held >= LONG_PRESS_MS) {
      Serial.println("Long press -> typing message");
      // Type one character at a time with a short pause,
      // so the phone/laptop doesn't drop keystrokes.
      for (const char* p = MESSAGE; *p; p++) {
        bleKeyboard.write(*p);
        delay(25);
      }
    } else {
      Serial.println("Short press -> play/pause");
      bleKeyboard.write(KEY_MEDIA_PLAY_PAUSE);
    }
  }
}
