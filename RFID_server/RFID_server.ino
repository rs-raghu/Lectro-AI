#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 5
#define RST_PIN 22

const char* ssid = "RS Raghu";
const char* password = "6380779185";

// Flask server address
const char* cloudServer = "http://192.168.114.115:5000";

// List of authorized RFID UIDs (normalized to lowercase)
const char* authorizedUIDs[] = {
    "53cb1229", 
    "aabbccdd", 
    "faeebcdb"
};
const int numAuthorizedUIDs = sizeof(authorizedUIDs) / sizeof(authorizedUIDs[0]);

MFRC522 rfid(SS_PIN, RST_PIN);
WebServer server(80);

bool isRecording = false;
String activeUID = "";
String lastScannedUID = "None";

// Get UID as a lowercase string
String getScannedUID() {
    String uid = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
        uid += String(rfid.uid.uidByte[i], HEX);
    }
    uid.toLowerCase();  // Ensure lowercase format
    return uid;
}

// Check if UID is authorized
bool isAuthorized(String scannedUID) {
    for (int i = 0; i < numAuthorizedUIDs; i++) {
        if (scannedUID == String(authorizedUIDs[i])) {
            return true;
        }
    }
    return false;
}

// Send HTTP request to Flask server
bool sendToCloud(String endpoint, String scannedUID) {
    HTTPClient http;
    String fullURL = String(cloudServer) + endpoint;
    Serial.print("[HTTP] Sending to: ");
    Serial.println(fullURL);

    http.begin(fullURL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(5000);  // ✅ Set reasonable timeout (5 sec)

    String payload = "{\"uid\": \"" + scannedUID + "\"}";
    int httpCode = http.POST(payload);
    bool success = (httpCode == 200);

    if (success) {
        Serial.println("[HTTP] Success!");
    } else {
        Serial.print("[HTTP] Failed! Code: ");
        Serial.println(httpCode);
    }

    http.end();
    return success;
}

// Root web page
void handleRoot() {
    String html = "<html><head>"
                  "<script>"
                  "function updateStatus() {"
                  " fetch('/rfid-status').then(response => response.text()).then(data => {"
                  "   let parts = data.split(',');"
                  "   document.getElementById('rfidDisplay').innerHTML = parts[0];"
                  "   document.getElementById('statusDisplay').innerHTML = parts[1];"
                  " });"
                  "} setInterval(updateStatus, 1000);"
                  "</script>"
                  "</head><body>"
                  "<h1>ESP32 Web Server</h1>"
                  "<p>Last Scanned RFID: <b><span id='rfidDisplay'>" + lastScannedUID + "</span></b></p>"
                  "<p>Recording Status: <b><span id='statusDisplay'>" + (isRecording ? "Recording in Progress" : "Stopped") + "</span></b></p>"
                  "</body></html>";

    server.send(200, "text/html", html);
}

// RFID status handler
void handleRFIDStatus() {
    server.send(200, "text/plain", lastScannedUID + "," + (isRecording ? "Recording in Progress" : "Stopped"));
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n[ESP32] Booting...");

    // Initialize RFID module
    SPI.begin();
    rfid.PCD_Init();
    Serial.println("[ESP32] RFID Initialized.");

    // WiFi Connection with timeout
    WiFi.begin(ssid, password);
    Serial.print("[WiFi] Connecting");
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WiFi] Connected!");
        Serial.print("[WiFi] IP Address: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n[WiFi] Connection Failed! Running offline...");
    }

    // Start web server
    server.on("/", handleRoot);
    server.on("/rfid-status", handleRFIDStatus);
    server.begin();
    Serial.println("[Server] Web Server Started!");
}

void loop() {
    server.handleClient();

    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
        return;
    }

    lastScannedUID = getScannedUID();
    Serial.print("[RFID] Scanned UID: ");
    Serial.println(lastScannedUID);

    if (!isAuthorized(lastScannedUID)) {
        Serial.println("[RFID] Unauthorized UID! Access Denied.");
        return;
    }

    if (isRecording) {
        if (lastScannedUID == activeUID) {
            Serial.println("[RFID] Stopping recording...");
            isRecording = !sendToCloud("/stop", lastScannedUID);
            activeUID = "";
        } else {
            Serial.println("[RFID] Another ID is in progress. Please wait.");
        }
    } else {
        Serial.println("[RFID] Starting recording...");
        if (sendToCloud("/start", lastScannedUID)) {
            isRecording = true;
            activeUID = lastScannedUID;
        }
    }

    delay(1000);

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
}
