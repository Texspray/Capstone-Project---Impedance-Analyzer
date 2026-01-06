/**
 * @file AD5933.cpp
 * @brief Library code for AD5933
 */

#include "AD5933.h"
#include <math.h>

extern I2C_HandleTypeDef hi2c1;

// --- INICIALIZAÇÃO DA VARIÁVEL ESTÁTICA ---
// Valor padrão (interno) = 16.776 MHz
unsigned long AD5933::clockSpeed = 16776000;

// --- IMPLEMENTAÇÃO DA NOVA FUNÇÃO ---
void AD5933::setExtClockFrequency(unsigned long freq) {
    clockSpeed = freq;
}

// -------------------------------------

int AD5933::getByte(uint8_t address, uint8_t *value) {
    HAL_StatusTypeDef status;
    uint8_t set_ptr_cmd[2];
    set_ptr_cmd[0] = ADDR_PTR;
    set_ptr_cmd[1] = address;

    status = HAL_I2C_Master_Transmit(&hi2c1, (AD5933_ADDR << 1), set_ptr_cmd, 2, 100);
    if (status != HAL_OK) return false;

    status = HAL_I2C_Master_Receive(&hi2c1, (AD5933_ADDR << 1) | 1, value, 1, 100);
    return (status == HAL_OK);
}

bool AD5933::sendByte(uint8_t address, uint8_t value) {
    uint8_t buffer[2];
    buffer[0] = address;
    buffer[1] = value;
    HAL_StatusTypeDef status = HAL_I2C_Master_Transmit(&hi2c1, (AD5933_ADDR << 1), buffer, 2, 100);
    return (status == HAL_OK);
}

bool AD5933::setControlMode(uint8_t mode) {
    uint8_t val;
    if (!getByte(CTRL_REG1, &val)) return false;
    val &= 0x0F;
    val |= mode;
    return sendByte(CTRL_REG1, val);
}

bool AD5933::reset() {
    uint8_t val;
    if (!getByte(CTRL_REG2, &val)) return false;
    val |= CTRL_RESET;
    return sendByte(CTRL_REG2, val);
}

bool AD5933::enableTemperature(uint8_t enable) {
    if (enable == TEMP_MEASURE) {
        return setControlMode(CTRL_TEMP_MEASURE);
    } else {
        return setControlMode(CTRL_NO_OPERATION);
    }
}

double AD5933::getTemperature() {
    if (enableTemperature(TEMP_MEASURE)) {
        while((readStatusRegister() & STATUS_TEMP_VALID) != STATUS_TEMP_VALID) ;
        uint8_t rawTemp[2];
        if (getByte(TEMP_DATA_1, &rawTemp[0]) && getByte(TEMP_DATA_2, &rawTemp[1])) {
            int rawTempVal = (rawTemp[0] << 8 | rawTemp[1]) & 0x1FFF;
            if ((rawTemp[0] & (1<<5)) == 0) {
                return rawTempVal / 32.0;
            } else {
                return (rawTempVal - 16384) / 32.0;
            }
        }
    }
    return -1;
}

bool AD5933::setClockSource(uint8_t source) {
    switch (source) {
        case CLOCK_EXTERNAL:
            return sendByte(CTRL_REG2, CTRL_CLOCK_EXTERNAL);
        case CLOCK_INTERNAL:
            return sendByte(CTRL_REG2, CTRL_CLOCK_INTERNAL);
        default:
            return false;
    }
}

bool AD5933::setInternalClock(bool internal) {
    if (internal)
        return setClockSource(CLOCK_INTERNAL);
    else
        return setClockSource(CLOCK_EXTERNAL);
}

bool AD5933::setSettlingCycles(int time) {
    int cycles;
    uint8_t settleTime[2], rsTime[2], val;
    settleTime[0] = time & 0xFF;        
    settleTime[1] = (time >> 8) & 0xFF; 
    cycles = (settleTime[0] | (settleTime[1] & 0x1));
    val = (uint8_t)((settleTime[1] & 0x7) >> 1);
    if ((cycles > 0x1FF) || !(val == 0 || val == 1 || val == 3)) return false;
    if (sendByte(NUM_SCYCLES_1, settleTime[1]) && (sendByte(NUM_SCYCLES_2, settleTime[0]))) {
        if (getByte(NUM_SCYCLES_1, &rsTime[1]) && getByte(NUM_SCYCLES_2, &rsTime[0])) {
            if ((settleTime[0] == rsTime[0]) && (settleTime[1] == rsTime[1])) return true;
        }
    }
    return false;
}

bool AD5933::setStartFrequency(unsigned long start) {
    // Usa a variável clockSpeed (agora dinâmica)
    long freqHex = (start / (clockSpeed / 4.0)) * pow(2, 27);
    if (freqHex > 0xFFFFFF) return false;
    uint8_t highByte = (freqHex >> 16) & 0xFF;
    uint8_t midByte = (freqHex >> 8) & 0xFF;
    uint8_t lowByte = freqHex & 0xFF;
    return sendByte(START_FREQ_1, highByte) &&
           sendByte(START_FREQ_2, midByte) &&
           sendByte(START_FREQ_3, lowByte);
}

bool AD5933::setIncrementFrequency(unsigned long increment) {
    // Usa a variável clockSpeed (agora dinâmica)
    long freqHex = (increment / (clockSpeed / 4.0)) * pow(2, 27);
    if (freqHex > 0xFFFFFF) return false;
    uint8_t highByte = (freqHex >> 16) & 0xFF;
    uint8_t midByte = (freqHex >> 8) & 0xFF;
    uint8_t lowByte = freqHex & 0xFF;
    return sendByte(INC_FREQ_1, highByte) &&
           sendByte(INC_FREQ_2, midByte) &&
           sendByte(INC_FREQ_3, lowByte);
}

bool AD5933::setNumberIncrements(unsigned int num) {
    if (num > 511) return false;
    uint8_t highByte = (num >> 8) & 0xFF;
    uint8_t lowByte = num & 0xFF;
    return sendByte(NUM_INC_1, highByte) && sendByte(NUM_INC_2, lowByte);
}

bool AD5933::setPGAGain(uint8_t gain) {
    uint8_t val;
    if (!getByte(CTRL_REG1, &val)) return false;
    val &= 0xFE;
    if (gain == PGA_GAIN_X1 || gain == 1) {
        val |= PGA_GAIN_X1;
        return sendByte(CTRL_REG1, val);
    } else if (gain == PGA_GAIN_X5 || gain == 5) {
        val |= PGA_GAIN_X5;
        return sendByte(CTRL_REG1, val);
    } else {
        return false;
    }
}

uint8_t AD5933::readRegister(uint8_t reg) {
    uint8_t val;
    if (getByte(reg, &val)) {
        return val;
    } else {
        return STATUS_ERROR;
    }
}

bool AD5933::setRange(uint8_t range) {
    uint8_t val;
    if(!getByte(CTRL_REG1, &val)) return false;
    val &=  0xF9;
    switch (range) {
        case CTRL_OUTPUT_RANGE_2: val |= CTRL_OUTPUT_RANGE_2; break;
        case CTRL_OUTPUT_RANGE_3: val |= CTRL_OUTPUT_RANGE_3; break;
        case CTRL_OUTPUT_RANGE_4: val |= CTRL_OUTPUT_RANGE_4; break;
        default: val |= CTRL_OUTPUT_RANGE_1; break;
    }
    return sendByte(CTRL_REG1, val);
}

uint8_t AD5933::readStatusRegister() {
    return readRegister(STATUS_REG);
}

int AD5933::readControlRegister() {
    return ((readRegister(CTRL_REG1) << 8) | readRegister(CTRL_REG2)) & 0xFFFF;
}

bool AD5933::getComplexData(int *real, int *imag) {
    while ((readStatusRegister() & STATUS_DATA_VALID) != STATUS_DATA_VALID);
    uint8_t realComp[2];
    uint8_t imagComp[2];
    if (getByte(REAL_DATA_1, &realComp[0]) &&
        getByte(REAL_DATA_2, &realComp[1]) &&
        getByte(IMAG_DATA_1, &imagComp[0]) &&
        getByte(IMAG_DATA_2, &imagComp[1]))
    {
        *real = (int16_t)(((realComp[0] << 8) | realComp[1]) & 0xFFFF);
        *imag = (int16_t)(((imagComp[0] << 8) | imagComp[1]) & 0xFFFF);
        return true;
    } else {
        *real = -1;
        *imag = -1;
        return false;
    }
}

bool AD5933::setPowerMode(uint8_t level) {
    switch (level) {
        case POWER_ON: return setControlMode(CTRL_NO_OPERATION);
        case POWER_STANDBY: return setControlMode(CTRL_STANDBY_MODE);
        case POWER_DOWN: return setControlMode(CTRL_POWER_DOWN_MODE);
        default: return false;
    }
}

bool AD5933::frequencySweep(int real[], int imag[], int n) {
    if (!(setPowerMode(POWER_STANDBY) &&
          setControlMode(CTRL_INIT_START_FREQ) &&
          setControlMode(CTRL_START_FREQ_SWEEP)))
          {
              return false;
          }
    int i = 0;
    while ((readStatusRegister() & STATUS_SWEEP_DONE) != STATUS_SWEEP_DONE) {
        if (i >= n) return false;
        if (!getComplexData(&real[i], &imag[i])) return false;
        i++;
        setControlMode(CTRL_INCREMENT_FREQ);
    }
    return setPowerMode(POWER_STANDBY);
}

bool AD5933::calibrate(int real[], int imag[], double gain[], double phase[], long int ref, int n) {
    if (!frequencySweep(real, imag, n)) return false;
    for (int i = 0; i < n; i++) {
        double magnitude = sqrt(pow((double)real[i], 2) + pow((double)imag[i], 2));
        gain[i] = (1.0 / ref) / magnitude;
        phase[i] = (atan2((double)imag[i], (double)real[i]) * 180.0 )/ 3.1415;
    }
    return true;
}