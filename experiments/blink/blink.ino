// Step 1: Blink test for the ELEGOO ESP32 (classic ESP32-WROOM-32)
// Board: Tools > Board > esp32 > "ESP32 Dev Module"
// Most ESP32 dev boards have a blue LED on GPIO 2.

const int LED = 2;

void setup() {
  Serial.begin(115200);
  pinMode(LED, OUTPUT);
  Serial.println("ESP32 alive! Blinking...");
}

void loop() {
  digitalWrite(LED, HIGH);
  delay(500);
  digitalWrite(LED, LOW);
  delay(500);
}
