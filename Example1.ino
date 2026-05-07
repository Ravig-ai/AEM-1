/*
 * haptic_signal_driver.ino
 * AEM 2026 — Haptic feedback firmware for Black Pill STM32F411
 *
 * Reads "SIGNAL:A/B/C/D" from the Python experiment app over USB serial.
 * Maps each button letter to a distinct vibration frequency and drives
 * the haptic actuator through:
 *   Black Pill → SPI → PIXI Click (MAX11300 DAC port 0)
 *               → 3.5 mm AUX → AudioAmp 2 Click → actuator
 *
 * Wiring (SPI):
 *   MOSI  PA7
 *   MISO  PA6
 *   SCLK  PA5
 *   CS    PA4
 *   CNVT  PB0
 *
 * Copy MAX11300.h / MAX11300.cpp / MAX11300registers.h into this sketch folder.
 */

#include <SPI.h>
#include "MAX11300.h"

#define M_PI     3.1415926535897932384626433832795f
#define CNVT_PIN PB0
#define CS_PIN   PA4
#define OUT_PIN0 0

MAX11300 pixi(&SPI, CNVT_PIN, CS_PIN);

// ── Haptic parameters ────────────────────────────────────────
// Assign a distinct frequency to each button so participants feel
// a different vibration cue per button press.
// Tune these to your actuator's sweet spot — e.g. 170 Hz for VLV101040A.
const uint16_t SAMPLE_RATE   = 50000;   // Hz — matches 20 µs update interval
const float    AMPLITUDE     = 25.0f;   // DAC units (conservative; matches example)
const uint32_t BUZZ_MS       = 80;      // Pulse duration in milliseconds

float freqForLetter(char c) {
  switch (c) {
    case 'A': return 150.0f;   // baseline — same as kit example
    case 'B': return 200.0f;
    case 'C': return 170.0f;   // near resonance of wide-band LRA
    case 'D': return 120.0f;
    default:  return 0.0f;
  }
}

// ── Phase accumulator (matches your example's generateSample exactly) ───────
// Static phase persists across calls so the sine wave is continuous.
// Reset phase to 0 when starting a new buzz so each pulse starts cleanly.
float phaseRad = 0.0f;

int16_t generateSample(uint16_t sample_rate_hz, float frequency_hz, float amplitude) {
  float phase  = 2.0f * M_PI * frequency_hz * 1.0f / sample_rate_hz + phaseRad;
  float sample = (amplitude * sinf(phase) + amplitude) / 2.0f;
  phaseRad     = fmodf(phase, 2.0f * M_PI);
  return (int16_t)sample;
}

// ── Runtime state ────────────────────────────────────────────
float    activeFreq  = 0.0f;
bool     buzzing     = false;
uint32_t buzzStart   = 0;
String   serialBuf   = "";

void startBuzz(float freq) {
  activeFreq = freq;
  phaseRad   = 0.0f;   // reset phase for a clean pulse
  buzzStart  = millis();
  buzzing    = true;
}

void stopBuzz() {
  buzzing = false;
  pixi.writeAnalogPin(OUT_PIN0, 0);
}

// ── Setup ────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  pixi.begin();
  delay(1);                                          // chip stabilise

  pixi.setDACref(DACInternal);
  pixi.setPinMode(OUT_PIN0, analogOut);              // FUNCID
  delay(200);                                        // from datasheet
  pixi.setPinDACrange(OUT_PIN0, DACZeroTo10);        // FUNCPRM
  delayMicroseconds(200);                            // from datasheet
  pixi.writeAnalogPin(OUT_PIN0, 0);

  Serial.println("Setup complete");
}

// ── Main loop ────────────────────────────────────────────────
void loop() {
  static unsigned long lastUpdateTime = 0;
  const  unsigned long updateInterval = 20;          // 20 µs → 50 kHz sample rate

  // 1. Parse incoming serial — accumulate until newline
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      serialBuf.trim();
      if (serialBuf.startsWith("SIGNAL:") && serialBuf.length() >= 8) {
        char   letter = serialBuf.charAt(7);
        float  freq   = freqForLetter(letter);
        if (freq > 0.0f) {
          startBuzz(freq);
        }
      }
      serialBuf = "";
    } else {
      if (serialBuf.length() < 32) serialBuf += c;
    }
  }

  // 2. Stop buzz after BUZZ_MS
  if (buzzing && (millis() - buzzStart >= BUZZ_MS)) {
    stopBuzz();
  }

  // 3. DAC output at 50 kHz — identical timing to your example
  unsigned long currentTime = micros();
  if (currentTime - lastUpdateTime >= updateInterval) {
    lastUpdateTime = currentTime;

    if (buzzing) {
      int16_t val = generateSample(SAMPLE_RATE, activeFreq, AMPLITUDE);
      pixi.writeAnalogPin(OUT_PIN0, val);
    }
  }
}