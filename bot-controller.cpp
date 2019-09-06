///
/// WeChat Jump Bot
/// Copyright (c) 2019 by SilentByte <https://silentbyte.com/>
///

#include <Servo.h>

constexpr int ACTIVE_PIN = 3;
constexpr int PITCH_PIN = 7;
constexpr int PITCH_UP = 15;
constexpr int PITCH_DOWN = 32;

Servo pitch_servo;

bool is_down = false;

void setup() {
    Serial.begin(9600);

    pinMode(ACTIVE_PIN, OUTPUT);
    digitalWrite(ACTIVE_PIN, LOW);

    pitch_servo.attach(PITCH_PIN);
    pitch_servo.write(PITCH_UP);
}

void up() {
    if(!is_down) {
        return;
    }

    digitalWrite(ACTIVE_PIN, LOW);
    pitch_servo.write(PITCH_UP);

    is_down = false;
}

void down() {
    if(is_down) {
        return;
    }

    digitalWrite(ACTIVE_PIN, HIGH);
    pitch_servo.write(PITCH_DOWN);

    is_down = true;
}

void loop() {
    if(Serial.available() > 0) {
        if(Serial.read() == 'D') {
            down();
        } else {
            up();
        }
    }
}
