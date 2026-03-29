#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Preferences.h>

#define SS_PIN 5
#define RST_PIN 22
#define MAX_RETRIES 3

// Configuration
const char* cloudServer = "http://192.168.114.115:5000";
const char* authorizedUIDs[] = {"53cb1229", "aabbccdd", "faeebcdb"};
const int numAuthorizedUIDs = sizeof(authorizedUIDs) / sizeof(authorizedUIDs[0]);

// Hardware
MFRC522 rfid(SS_PIN, RST_PIN);
WebServer server(80);
Preferences prefs;

// State
volatile bool isRecording = false;
char activeUID[9] = {0}; // 8 chars + null
char lastScannedUID[9] = "None";

// ---------------------
// Setup Functionality
// ---------------------
void setup() {
    Serial.begin(115200);
    SPI.begin();
    rfid.PCD_Init();

    // Load WiFi credentials from NVS and connect
    prefs.begin("wifi-creds");
    connectToWiFi();

    // Start web server
    server.on("/", handleRoot);
    server.on("/rfid-status", handleRFIDStatus);
    server.begin();

    Serial.println("[ESP32] Setup complete.");
}

// ---------------------
// Main Loop Functionality
// ---------------------
void loop() {
    server.handleClient();
    handleRFID();
    testConsecutiveScans(); // Test case 1: Consecutive scans
    testWiFiDrop();         // Test case 3: WiFi drop simulation
}

// ---------------------
// Core RFID Handling
// ---------------------
void handleRFID() {
    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;

    char uid[9];
    getScannedUID(uid); // Populates UID as char array

    Serial.print("[RFID] Scanned: ");
    Serial.println(uid);

    if (!isAuthorized(uid)) {
        Serial.println("[RFID] Unauthorized!");
        return;
    }

    if (isRecording) {
        if (strcmp(uid, activeUID) == 0) {
            stopRecording(uid);
        }
    } else {
        startRecording(uid);
    }

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
}

// ---------------------
// Helper Functions
// ---------------------
void getScannedUID(char* output) {
    memset(output, 0, 9);
    for (byte i = 0; i < rfid.uid.size; i++) {
        sprintf(output + i * 2, "%02x", rfid.uid.uidByte[i]);
    }
}

bool isAuthorized(const char* uid) {
    for (int i = 0; i < numAuthorizedUIDs; i++) {
        if (strcmp(uid, authorizedUIDs[i]) == 0) return true;
    }
    return false;
}

void startRecording(const char* uid) {
    if (sendToCloud("/start", uid)) {
        isRecording = true;
        strncpy(activeUID, uid, 8);
        Serial.println("[RFID] Recording started.");
    }
}

void stopRecording(const char* uid) {
    if (sendToCloud("/stop", uid)) {
        isRecording = false;
        memset(activeUID, 0, 9);
        Serial.println("[RFID] Recording stopped.");
    }
}

bool sendToCloud(const char* endpoint, const char* uid) {
    WiFiClient client;
    HTTPClient http;

    String url = String(cloudServer) + endpoint;
    http.begin(client, url);
    http.addHeader("Content-Type", "application/json");

    String payload = "{\"uid\":\"" + String(uid) + "\"}";
    int code = http.POST(payload);

    http.end();
    
    return (code == 200);
}

// ---------------------
// Web Interface
// ---------------------
void handleRoot() {
    String html = R"=====(
      <html><head>
      <script>
      async function updateStatus() {
        const res = await fetch('/rfid-status');
        const [uid, status] = (await res.text()).split(',');
        document.getElementById('uid').innerText = uid;
        document.getElementById('status').innerText = status; 
      }
      setInterval(updateStatus, 1000);
      </script></head>
      <body>
        <h1>RFID Audio Recorder</h1>
        <p>Last UID: <b id="uid">%UID%</b></p>
        <p>Status: <b id="status">%STATUS%</b></p>
      </body></html>
      )=====";

    html.replace("%UID%", lastScannedUID);
    html.replace("%STATUS%", isRecording ? "Recording" : "Stopped");
    
    server.send(200, "text/html", html);
}

void handleRFIDStatus() {
    String response = String(lastScannedUID) + ",";
    response += isRecording ? "Recording" : "Stopped";
    
    server.send(200, "text/plain", response);
}

// ---------------------
// WiFi Management
// ---------------------
void connectToWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;

    String ssid = prefs.getString("ssid", "");
    String pass = prefs.getString("pass", "");

    if (ssid == "") {
        Serial.println("[WiFi] No saved credentials!");
        return;
    }

    WiFi.begin(ssid.c_str(), pass.c_str());
    
    for (int i = 0; i < 20; i++) {
        if (WiFi.status() == WL_CONNECTED) break;
        delay(500);
        Serial.print(".");
    }

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("\n[WiFi] Connection failed!");
        return;
    }

    Serial.print("\n[WiFi] Connected! IP Address: ");
    Serial.println(WiFi.localIP());
}

// ---------------------
// Test Cases
// ---------------------

void testConsecutiveScans() { // Test case for consecutive scans
  static unsigned long lastTest = 0;
  
  if (millis() - lastTest < 5000) return; // Run every 5 seconds
  
  Serial.println("\n[TEST] Starting consecutive scan test...");
  
  for (int i=0; i<5; i++) { // Simulate rapid taps of the same UID
      rfid.uid.size = 4;
      rfid.uid.uidByte[0] = 0x53;
      rfid.uid.uidByte[1] = 0xcb;
      rfid.uid.uidByte[2] = 0x12;
      rfid.uid.uidByte[3] = 0x29;

      handleRFID(); // Process simulated scan
      delay(100);   // Simulate rapid taps
  }
  
  lastTest = millis();
}

void testWiFiDrop() { // Test case for WiFi drop simulation
  static bool wifiOff = false;
  static unsigned long lastTest = 0;

  if (millis() - lastTest < 30000) return; // Run every 30 seconds

  if (!wifiOff) {
      Serial.println("\n[TEST] Simulating WiFi disconnect...");
      WiFi.disconnect();
      wifiOff = true;
  } else {
      Serial.println("\n[TEST] Reconnecting WiFi...");
      WiFi.reconnect();
      wifiOff = false;
  }

  lastTest = millis();
}
