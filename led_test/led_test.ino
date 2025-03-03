void setup() {
    pinMode(2, OUTPUT);  // GPIO 2 is the built-in LED on most ESP32 boards
    Serial.begin(115200);
    Serial.println("ESP32 LED Blink Test Starting...");
}

void loop() {
    Serial.println("LED ON");
    digitalWrite(2, HIGH);  // Turn LED on
    delay(1000);
    
    Serial.println("LED OFF");
    digitalWrite(2, LOW);   // Turn LED off
    delay(1000);
}
