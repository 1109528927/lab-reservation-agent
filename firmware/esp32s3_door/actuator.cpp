#include "actuator.h"

#include <Arduino.h>

#include "config.h"

static void buzzerIdle() {
#if BUZZER_ACTIVE_LOW
  digitalWrite(PIN_BUZZER, HIGH);
#else
  digitalWrite(PIN_BUZZER, LOW);
#endif
}

static void buzzerOn() {
#if BUZZER_ACTIVE_LOW
  digitalWrite(PIN_BUZZER, LOW);
#else
  digitalWrite(PIN_BUZZER, HIGH);
#endif
}

static void beep(int ms) {
  buzzerOn();
  delay(ms);
  buzzerIdle();
}

void actuatorBegin() {
  pinMode(PIN_LED_ALLOW, OUTPUT);
  pinMode(PIN_LED_DENY, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_LED_ALLOW, LOW);
  digitalWrite(PIN_LED_DENY, LOW);
  buzzerIdle();
}

void actAllow() {
  digitalWrite(PIN_LED_DENY, LOW);
  digitalWrite(PIN_LED_ALLOW, HIGH);
  beep(120);
  delay(80);
  beep(120);
  delay(400);
  digitalWrite(PIN_LED_ALLOW, LOW);
}

void actDeny() {
  digitalWrite(PIN_LED_ALLOW, LOW);
  digitalWrite(PIN_LED_DENY, HIGH);
  beep(DENY_BEEP_MS);
  digitalWrite(PIN_LED_DENY, LOW);
}
