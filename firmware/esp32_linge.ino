#include <ETH.h>
#include <HTTPClient.h>
#include <HardwareSerial.h>

// Adapter ces broches au câblage réel du MU910-M et à la carte ESP32 Ethernet.
HardwareSerial rfid(2);
constexpr int RFID_RX = 16;
constexpr int RFID_TX = 17;
const char* API_URL = "http://192.168.1.10:5000/api/scan";

void setup() {
  Serial.begin(115200);
  rfid.begin(115200, SERIAL_8N1, RFID_RX, RFID_TX);
  ETH.begin();
  while (!ETH.linkUp()) delay(100);
}

void sendEpc(const String& epc) {
  if (!ETH.linkUp()) return;
  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");
  http.POST(String("{\"epc\":\"") + epc + "\"}");
  http.end();
}

void loop() {
  // Le protocole UART exact dépend du firmware MU910-M. Cette version attend
  // une ligne EPC terminée par CR/LF, pratique pour un mode émulation/validation.
  if (rfid.available()) {
    String epc = rfid.readStringUntil('\n');
    epc.trim();
    if (epc.length() > 0) sendEpc(epc);
  }
  delay(20);
}
