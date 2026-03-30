
#pragma once

// ----- WiFi -----
#define WIFI_SSID     "RS Raghu"
#define WIFI_PASSWORD "6380779185"

// ----- Flask server -----
#define FLASK_SERVER_URL "http://10.236.162.115:5000"

// Shared secret — must match FLASK_AUTH_TOKEN in your .env file
// Generate one: python -c "import secrets; print(secrets.token_hex(32))"
#define AUTH_TOKEN "4bf1795e35fd9d45ed3f4474c283561d556fa422acd64b028aae13179e85d228"

// ----- Authorized RFID UIDs -----
const char* AUTHORIZED_UIDS[]  = { "53cb1229", "aabbccdd" };
const int   NUM_AUTHORIZED_UIDS = 2;
