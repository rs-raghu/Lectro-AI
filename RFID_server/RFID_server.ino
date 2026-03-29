/*
 * RFID_server.ino — ESP32 RFID Recorder Controller
 *
 * Tap an authorized RFID card to start recording on the Flask server.
 * Tap the same card again to stop.
 *
 * Requires: config.h in the same folder (not committed to version control)
 * Libraries: MFRC522, WiFi, HTTPClient, WebServer (all via Arduino Library Manager)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <SPI.h>
#include <MFRC522.h>
#include "config.h"

// ---- Pin definitions ----
#define SS_PIN  5
#define RST_PIN 22

// ---- Debounce: ignore re-scans within this window ----
#define SCAN_COOLDOWN_MS 2500

// ---- Globals ----
MFRC522  rfid(SS_PIN, RST_PIN);
WebServer server(80);

volatile bool isRecording  = false;
char activeUID[9]          = {0};      // UID that opened the current session
char lastScannedUID[9]     = "None";
unsigned long lastScanTime = 0;

// =============================================================================
// UID helpers
// =============================================================================

/** Read the scanned card's UID into a zero-padded lowercase hex string. */
void getUID(char* output) {
    memset(output, 0, 9);
    for (byte i = 0; i < rfid.uid.size && i < 4; i++) {
        sprintf(output + i * 2, "%02x", rfid.uid.uidByte[i]);
    }
}

/** Check whether a UID is in the AUTHORIZED_UIDS list from config.h. */
bool isAuthorized(const char* uid) {
    for (int i = 0; i < NUM_AUTHORIZED_UIDS; i++) {
        if (strcmp(uid, AUTHORIZED_UIDS[i]) == 0) return true;
    }
    return false;
}

// =============================================================================
// HTTP communication with Flask
// =============================================================================

/**
 * Send a POST request to the Flask server.
 * Auth token is sent as a custom header so it never appears in the URL.
 * Returns true only on HTTP 200.
 */
bool sendToFlask(const char* endpoint, const char* uid) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[HTTP] No WiFi — skipping request.");
        return false;
    }

    WiFiClient client;
    HTTPClient http;

    String url = String(FLASK_SERVER_URL) + endpoint;
    http.begin(client, url);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Auth-Token", AUTH_TOKEN);   // shared secret
    http.setTimeout(5000);

    String payload = "{\"uid\":\"" + String(uid) + "\"}";
    int code = http.POST(payload);
    String body = http.getString();
    http.end();

    Serial.printf("[HTTP] %s → %d  %s\n", endpoint, code, body.c_str());
    return (code == 200);
}

// =============================================================================
// RFID scan handler
// =============================================================================

void handleRFID() {
    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;

    // Ignore rapid / accidental double-taps
    unsigned long now = millis();
    if (now - lastScanTime < SCAN_COOLDOWN_MS) {
        rfid.PICC_HaltA();
        rfid.PCD_StopCrypto1();
        return;
    }
    lastScanTime = now;

    char uid[9];
    getUID(uid);
    strncpy(lastScannedUID, uid, 9);
    Serial.printf("[RFID] Scanned: %s\n", uid);

    if (!isAuthorized(uid)) {
        Serial.println("[RFID] Unauthorized card. Access denied.");
        rfid.PICC_HaltA();
        rfid.PCD_StopCrypto1();
        return;
    }

    if (isRecording) {
        if (strcmp(uid, activeUID) == 0) {
            // Same card that started the session — stop it
            Serial.println("[RFID] Stopping recording...");
            if (sendToFlask("/stop", uid)) {
                isRecording = false;
                memset(activeUID, 0, 9);
                Serial.println("[RFID] Recording stopped.");
            } else {
                Serial.println("[RFID] Stop request failed. Try again.");
            }
        } else {
            // Different card tapped while a session is active
            Serial.printf("[RFID] Session owned by %s — wait for it to end.\n", activeUID);
        }
    } else {
        Serial.println("[RFID] Starting recording...");
        if (sendToFlask("/start", uid)) {
            isRecording = true;
            strncpy(activeUID, uid, 9);
            Serial.printf("[RFID] Recording started. Session UID: %s\n", activeUID);
        } else {
            Serial.println("[RFID] Start request failed. Check server.");
        }
    }

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
}

// =============================================================================
// WiFi
// =============================================================================

void connectWiFi() {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("[WiFi] Connecting");
    for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) {
        delay(500);
        Serial.print(".");
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WiFi] Connected. IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[WiFi] Failed. Running in offline mode.");
    }
}

// =============================================================================
// Built-in web dashboard (served from the ESP32 itself)
// =============================================================================

void handleRoot() {
    // Placeholders replaced after the raw string
    String html = R"=====(<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RFID Recorder</title>
<style>
  body{font-family:sans-serif;max-width:480px;margin:2rem auto;padding:0 1rem}
  h2{margin-bottom:1rem}
  .row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee}
  .badge{padding:3px 10px;border-radius:10px;font-size:.85rem;font-weight:600}
  .on{background:#d1fae5;color:#065f46}
  .off{background:#f3f4f6;color:#374151}
</style>
<script>
async function refresh() {
  try {
    const d = await (await fetch('/status')).json();
    document.getElementById('uid').textContent    = d.uid;
    document.getElementById('status').className   = 'badge ' + (d.recording ? 'on' : 'off');
    document.getElementById('status').textContent = d.recording ? 'Recording' : 'Idle';
  } catch(e) {}
}
setInterval(refresh, 1500);
</script>
</head><body>
<h2>RFID Recorder</h2>
<div class="row"><span>Last UID</span><b id="uid">)=====";

    html += lastScannedUID;
    html += R"=====(</b></div>
<div class="row"><span>Status</span>
<span id="status" class="badge )=====";
    html += isRecording ? "on\">Recording" : "off\">Idle";
    html += R"=====(</span></div>
</body></html>)=====";

    server.send(200, "text/html", html);
}

/** JSON endpoint polled by the dashboard's JS every 1.5 s */
void handleStatus() {
    String json = "{\"uid\":\"";
    json += lastScannedUID;
    json += "\",\"recording\":";
    json += isRecording ? "true" : "false";
    json += "}";
    server.send(200, "application/json", json);
}

// =============================================================================
// Setup & Loop
// =============================================================================

void setup() {
    Serial.begin(115200);
    delay(500);

    SPI.begin();
    rfid.PCD_Init();
    Serial.println("[ESP32] RFID initialized.");

    connectWiFi();

    server.on("/",       handleRoot);
    server.on("/status", handleStatus);
    server.begin();
    Serial.println("[ESP32] Web server started.");
}

void loop() {
    // Auto-reconnect if WiFi drops
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[WiFi] Connection lost. Reconnecting...");
        WiFi.reconnect();
        delay(3000);
    }

    server.handleClient();
    handleRFID();
}
