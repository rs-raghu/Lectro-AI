#include <WiFi.h>
#include <WebServer.h>
#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 5    // ESP32 GPIO5 (SDA/SS)
#define RST_PIN 22  // ESP32 GPIO22 (RST)

const char* ssid = "RS Raghu";
const char* password = "6380779185";

MFRC522 rfid(SS_PIN, RST_PIN);
WebServer server(80);

unsigned long scanStopTime = 0;
const unsigned long stopDuration = 10000; // 10 seconds

String activeSessionID = "";
bool isRecording = false;
String lastScannedUID = "None"; // Store last scanned UID

// List of authorized UIDs
const String authorizedUIDs[] = {"53cb1229", "a9967db"};  
const int numAuthorizedUIDs = sizeof(authorizedUIDs) / sizeof(authorizedUIDs[0]);

// Webpage with JavaScript auto-refresh
void handleRoot() {
    String html = "<html><head>"
                  "<script>"
                  "function updateStatus() {"
                  " fetch('/rfid-status').then(response => response.text()).then(data => {"
                  "   let parts = data.split(',');"
                  "   document.getElementById('rfidDisplay').innerHTML = parts[0];"
                  "   document.getElementById('statusDisplay').innerHTML = parts[1];"
                  " });"
                  "}"
                  "setInterval(updateStatus, 1000);" // Refresh every second
                  "</script>"
                  "</head><body>"
                  "<h1>ESP32 Web Server</h1>"
                  "<p>Last Scanned RFID: <b><span id='rfidDisplay'>" + lastScannedUID + "</span></b></p>"
                  "<p>Recording Status: <b><span id='statusDisplay'>" + (isRecording ? "Recording in Progress" : "Stopped") + "</span></b></p>"
                  "</body></html>";

    server.send(200, "text/html", html);
}

// Return last scanned RFID & recording status
void handleRFIDStatus() {
    String status = isRecording ? "Recording in Progress" : "Stopped";
    server.send(200, "text/plain", lastScannedUID + "," + status);
}

void setup() {
    Serial.begin(115200);
    SPI.begin();
    rfid.PCD_Init();

    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi...");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nConnected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());

    server.on("/", handleRoot);
    server.on("/rfid-status", handleRFIDStatus);
    server.begin();
    Serial.println("Web Server Started!");
}

void loop() {
    server.handleClient();

    if (millis() < scanStopTime) {
        return;
    }

    if (scanStopTime != 0 && millis() >= scanStopTime) {
        Serial.println("Session ended. Resuming scanning...");
        activeSessionID = "";  
        scanStopTime = 0;
        isRecording = false;
    }

    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
        return;
    }

    // Read UID and convert to string
    lastScannedUID = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
        lastScannedUID += String(rfid.uid.uidByte[i], HEX);
    }
    lastScannedUID.toLowerCase();

    Serial.print("Scanned UID: ");
    Serial.println(lastScannedUID);

    // Check authorization
    bool isAuthorized = false;
    for (int i = 0; i < numAuthorizedUIDs; i++) {
        if (lastScannedUID == authorizedUIDs[i]) {
            isAuthorized = true;
            break;
        }
    }

    if (isAuthorized) {
        if (activeSessionID == "") { 
            Serial.println("Authentication successful! Starting recording...");
            activeSessionID = lastScannedUID;
            isRecording = true;
        } 
        else if (activeSessionID == lastScannedUID) { 
            Serial.println("Same ID detected. Pausing for 10 seconds...");
            scanStopTime = millis() + stopDuration;
            isRecording = false;
        } 
        else { 
            Serial.println("Another ID in progress! Wait for session to end.");
        }
    } 
    else {
        Serial.println("Authentication failed!");
    }

    // Immediately update web status
    handleRFIDStatus();

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
}
