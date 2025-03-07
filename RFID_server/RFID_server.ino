#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <SPI.h>
#include <MFRC522.h>

// Define RFID module pins
#define SS_PIN 5
#define RST_PIN 22

// WiFi credentials
const char* ssid = "RS Raghu";
const char* password = "6380779185";

// Flask server address
const char* cloudServer = "http://192.168.219.115:5000";

// List of authorized RFID UIDs
const char* authorizedUIDs[] = {
    "53cb1229",  // Example UID 1
    "aabbccdd",  // Example UID 2
    "deadbeef"   // Example UID 3
};
const int numAuthorizedUIDs = sizeof(authorizedUIDs) / sizeof(authorizedUIDs[0]);

// Initialize RFID and Web Server
MFRC522 rfid(SS_PIN, RST_PIN);
WebServer server(80);

bool isRecording = false;
String lastScannedUID = "None";

// Function to get RFID UID as a string
String getScannedUID() {
    String uid = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
        uid += String(rfid.uid.uidByte[i], HEX);
    }
    return uid;
}

// Function to check if scanned UID is authorized
bool isAuthorized(String scannedUID) {
    for (int i = 0; i < numAuthorizedUIDs; i++) {
        if (scannedUID.equalsIgnoreCase(authorizedUIDs[i])) {
            return true;
        }
    }
    return false;
}

// Function to send HTTP request to Flask server
bool sendToCloud(String endpoint, String scannedUID) {
    HTTPClient http;
    String fullURL = String(cloudServer) + endpoint;

    Serial.print("[HTTP] Sending to: ");
    Serial.println(fullURL);

    http.begin(fullURL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(15000);  // Increase timeout for slow networks

    String payload = "{\"uid\": \"" + scannedUID + "\"}";
    int httpCode = http.POST(payload);

    if (httpCode == 200) {  // Ensure only successful responses count
        Serial.println("[HTTP] Recording toggled successfully!");
        http.end();
        return true;
    } else {
        Serial.print("[HTTP] Request Failed! Code: ");
        Serial.println(httpCode);
        http.end();
        return false;
    }
}

// Handle root web page
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
    delay(2000);

    Serial.println("\n[ESP32] Booting...");

    // Initialize RFID module
    SPI.begin();
    rfid.PCD_Init();
    Serial.println("[ESP32] RFID Initialized.");

    // Connect to WiFi
    WiFi.begin(ssid, password);
    Serial.print("[WiFi] Connecting...");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n[WiFi] Connected!");
    Serial.print("[WiFi] IP Address: ");
    Serial.println(WiFi.localIP());

    // Setup web server
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

    isRecording = !isRecording ? sendToCloud("/start", lastScannedUID) : !sendToCloud("/stop", lastScannedUID);

    delay(2000);  // Prevent multiple rapid scans

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
}
