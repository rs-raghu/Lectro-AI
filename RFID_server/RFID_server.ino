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

// Flask server address (change this to your Flask server IP)
const char* cloudServer = "http://192.168.223.115:5000";

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

// Function to send HTTP request to Flask server
bool sendToCloud(String endpoint, String scannedUID) {
    HTTPClient http;
    String fullURL = String(cloudServer) + endpoint;

    Serial.print("[HTTP] Sending to: ");
    Serial.println(fullURL);

    http.begin(fullURL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(5000);

    String payload = "{\"uid\": \"" + scannedUID + "\"}";
    int httpCode = http.POST(payload);

    if (httpCode > 0) {
        Serial.println("[HTTP] Response: " + http.getString());
        http.end();
        return true;
    } else {
        Serial.println("[HTTP] Request Failed!");
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

    // Toggle recording state
    if (!isRecording) {
        Serial.println("[RFID] Starting Recording...");
        isRecording = sendToCloud("/start", lastScannedUID);
    } else {
        Serial.println("[RFID] Stopping Recording...");
        isRecording = !sendToCloud("/stop", lastScannedUID);
    }

    handleRFIDStatus();

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
}
