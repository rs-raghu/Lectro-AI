#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 5    // ESP32 GPIO5 (SDA/SS)
#define RST_PIN 22  // ESP32 GPIO22 (RST)

MFRC522 rfid(SS_PIN, RST_PIN);
unsigned long scanStopTime = 0;
const unsigned long stopDuration = 10000; // 10 seconds

String activeSessionID = "";  // Store active session UID

// List of authorized UIDs (lowercase for uniformity)
const String authorizedUIDs[] = {"53cb1229", "a9967db"};  
const int numAuthorizedUIDs = sizeof(authorizedUIDs) / sizeof(authorizedUIDs[0]);

void setup() {
    Serial.begin(115200);
    SPI.begin();
    rfid.PCD_Init();
    Serial.println("RFID Scanner Ready...");
}

void loop() {
    // If scanning is paused, wait until 10 seconds pass
    if (millis() < scanStopTime) {
        return;
    }

    // After pausing for 10 seconds, reset everything
    if (scanStopTime != 0 && millis() >= scanStopTime) {
        Serial.println("Session ended. Resuming scanning...");
        activeSessionID = ""; // Reset active session
        scanStopTime = 0;  // Reset timer
    }

    // Check for a new RFID card
    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
        return;
    }

    // Read UID and convert to a string (lowercase for uniformity)
    String currentUID = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
        currentUID += String(rfid.uid.uidByte[i], HEX);
    }
    currentUID.toLowerCase(); // Convert to lowercase for case-insensitive matching

    Serial.print("Scanned UID: ");
    Serial.println(currentUID);

    // Check if the UID is authorized
    bool isAuthorized = false;
    for (int i = 0; i < numAuthorizedUIDs; i++) {
        if (currentUID == authorizedUIDs[i]) {
            isAuthorized = true;
            break;
        }
    }

    if (isAuthorized) {
        if (activeSessionID == "") { 
            // No session active, start new session
            Serial.println("Authentication successful!");
            activeSessionID = currentUID;
        } 
        else if (activeSessionID == currentUID) { 
            // Same ID detected, pause session
            Serial.println("Same ID detected. Pausing for 10 seconds...");
            scanStopTime = millis() + stopDuration; // Pause for 10 sec
        } 
        else { 
            // Different authorized ID scanned during active session
            Serial.println("Another ID in progress! Wait for session to end.");
        }
    } 
    else {
        Serial.println("Authentication failed!");
    }

    // Halt card communication
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
}
