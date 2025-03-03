#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 5    // ESP32 GPIO5 (SDA/SS)
#define RST_PIN 22  // ESP32 GPIO22 (RST)

const char* ssid = "RS Raghu";
const char* password = "6380779185";
const char* cloudServer = "http://192.168.238.115:5000";
  // Laptop's Flask Server IP

MFRC522 rfid(SS_PIN, RST_PIN);
WebServer server(80);

bool isRecording = false;
String lastScannedUID = "None"; 

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

void handleRFIDStatus() {
    String status = isRecording ? "Recording in Progress" : "Stopped";
    server.send(200, "text/plain", lastScannedUID + "," + status);
}

void setup() {
    Serial.begin(115200);
    while (!Serial); // Ensure Serial Monitor is ready
    Serial.println("\n\nBooting ESP32...");

    delay(2000); // Wait to make sure ESP32 is ready

    SPI.begin();
    Serial.println("SPI initialized.");
    
    rfid.PCD_Init();
    Serial.println("RFID module initialized.");

    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi");
    
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());

    server.on("/", handleRoot);
    server.on("/rfid-status", handleRFIDStatus);
    server.begin();
    Serial.println("Web Server Started!");

    Serial.flush(); // Ensure Serial prints are actually sent
}



void loop() {
    server.handleClient();

    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
        return;
    }

    lastScannedUID = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
        lastScannedUID += String(rfid.uid.uidByte[i], HEX);
    }
    lastScannedUID.toLowerCase();

    Serial.print("Scanned UID: ");
    Serial.println(lastScannedUID);

    if (!isRecording) {
    Serial.println("Starting recording...");
    isRecording = sendToCloud("/start", lastScannedUID);
} else {
    Serial.println("Stopping recording...");
    isRecording = !sendToCloud("/stop", lastScannedUID);
}


    handleRFIDStatus(); // Update web UI immediately

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
}

// ✅ Use HTTPClient for API calls
bool sendToCloud(String endpoint, String scannedUID) {
    HTTPClient http;
    String fullURL = String(cloudServer) + endpoint;

    Serial.print("Sending request to: ");
    Serial.println(fullURL);

    http.begin(fullURL);
    http.addHeader("Content-Type", "application/json");

    String payload = "{\"uid\": \"" + scannedUID + "\"}";
    int httpCode = http.POST(payload);

    if (httpCode > 0) {
        Serial.println("Server Response: " + http.getString());
        http.end();
        return true;
    } else {
        Serial.println("Failed to reach server!");
        http.end();
        return false;
    }
}


