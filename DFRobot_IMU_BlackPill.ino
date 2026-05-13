#include <Wire.h>
#include "DFRobot_ADXL345.h"
#include "DFRobot_BMP280.h"
#include "DFRobot_QMC5883.h"

DFRobot_ADXL345_I2C accel(&Wire, ADXL345_ADDR_ALT_LOW);
DFRobot_QMC5883 compass(&Wire, VCM5883L_ADDRESS);
typedef DFRobot_BMP280_IIC BMP;
BMP bmpLow(&Wire, BMP::eSdoLow);
BMP bmpHigh(&Wire, BMP::eSdoHigh);
BMP *bmp = nullptr;

#define SEA_LEVEL_PRESSURE 1013.25f

constexpr uint8_t ITG3200_ADDR = 0x68;
constexpr uint8_t ITG3200_REG_PWR_MGM = 0x3E;
constexpr uint8_t ITG3200_REG_SMPLRT_DIV = 0x15;
constexpr uint8_t ITG3200_REG_DLPF_FS = 0x16;
constexpr uint8_t ITG3200_REG_GYRO_XOUT = 0x1D;
constexpr float ITG3200_SCALE_DPS = 1.0f / 14.375f;

bool writeRegister(uint8_t address, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool readRegisters(uint8_t address, uint8_t reg, uint8_t *buffer, uint8_t length) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  uint8_t count = Wire.requestFrom(address, length);
  if (count != length) {
    return false;
  }

  for (uint8_t i = 0; i < length; i++) {
    buffer[i] = Wire.read();
  }
  return true;
}

int16_t makeInt16(uint8_t msb, uint8_t lsb) {
  return (int16_t)((msb << 8) | lsb);
}

bool initGyro() {
  return writeRegister(ITG3200_ADDR, ITG3200_REG_PWR_MGM, 0x00) &&
         writeRegister(ITG3200_ADDR, ITG3200_REG_SMPLRT_DIV, 0x07) &&
         writeRegister(ITG3200_ADDR, ITG3200_REG_DLPF_FS, 0x1B);
}

bool readGyro(float &gx, float &gy, float &gz) {
  uint8_t raw[6];
  if (!readRegisters(ITG3200_ADDR, ITG3200_REG_GYRO_XOUT, raw, 6)) {
    return false;
  }

  gx = makeInt16(raw[0], raw[1]) * ITG3200_SCALE_DPS;
  gy = makeInt16(raw[2], raw[3]) * ITG3200_SCALE_DPS;
  gz = makeInt16(raw[4], raw[5]) * ITG3200_SCALE_DPS;
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(PB7, PB6);
  Wire.setClock(100000);

  Serial.println("DFRobot SEN0140 accel + gyro test on STM32 Black Pill");
  Serial.println("Wiring:");
  Serial.println("  VIN -> 3V3");
  Serial.println("  GND -> GND");
  Serial.println("  SDA -> PB7");
  Serial.println("  SCL -> PB6");

  if (!accel.begin()) {
    Serial.println("ADXL345 init failed");
    while (1) {
    }
  }
  accel.powerOn();
  Serial.println("ADXL345 initialized correctly.");

  Serial.println("Starting ITG3200...");
  if (!initGyro()) {
    Serial.println("ITG3200 init failed");
    while (1) {
    }
  }
  Serial.println("ITG3200 initialized correctly.");

  Serial.println("Starting magnetometer...");
  if (!compass.begin()) {
    Serial.println("Magnetometer init failed");
    while (1) {
    }
  }
  Serial.println("Magnetometer initialized correctly.");

  Serial.println("Starting BMP280...");
  if (bmpLow.begin() == BMP::eStatusOK) {
    bmp = &bmpLow;
    Serial.println("BMP280 initialized correctly at 0x76.");
  } else if (bmpHigh.begin() == BMP::eStatusOK) {
    bmp = &bmpHigh;
    Serial.println("BMP280 initialized correctly at 0x77.");
  } else {
    Serial.println("BMP280 init failed");
    while (1) {
    }
  }
}

void loop() {
  int xyz[3];
  accel.readAccel(xyz);

  float gx = 0.0f;
  float gy = 0.0f;
  float gz = 0.0f;
  bool gyroOk = readGyro(gx, gy, gz);
  sVector_t mag = compass.readRaw();
  float temperature = bmp->getTemperature();
  uint32_t pressure = bmp->getPressure();
  float altitude = bmp->calAltitude(SEA_LEVEL_PRESSURE, pressure);

  //Serial.print("X: ");
  Serial.print(xyz[0]);
  Serial.print(","); //Y
  Serial.print(xyz[1]);
  Serial.print(","); //Z
  Serial.println(xyz[2]);
  delay(5);
}
