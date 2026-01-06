#include "Si5351.h"
#include <math.h> // Adicionado para pow()

// Handle I2C definido no main.cpp
extern I2C_HandleTypeDef hi2c1;

/**
 * @brief Escreve um byte em um registrador do Si5351.
 */
bool Si5351::sendByte(uint8_t reg, uint8_t value) {
    uint8_t buffer[2] = {reg, value};
    HAL_StatusTypeDef status = HAL_I2C_Master_Transmit(&hi2c1, SI5351_ADDRESS, buffer, 2, 100);
    return (status == HAL_OK);
}

/**
 * @brief Lê um byte de um registrador do Si5351.
 */
bool Si5351::readByte(uint8_t reg, uint8_t* value) {
    HAL_StatusTypeDef status;
    status = HAL_I2C_Master_Transmit(&hi2c1, SI5351_ADDRESS, &reg, 1, 100);
    if (status != HAL_OK) {
        return false;
    }
    status = HAL_I2C_Master_Receive(&hi2c1, SI5351_ADDRESS, value, 1, 100);
    return (status == HAL_OK);
}

/**
 * @brief Inicializa o Si5351.
 */
bool Si5351::init() {
    uint8_t dev_status;
    if (!readByte(SI5351_REG_0_DEVICE_STATUS, &dev_status)) {
        return false; // Falha na comunicação I2C
    }

    // Desliga todas as saídas por segurança
    if (!sendByte(SI5351_REG_3_OUTPUT_ENABLE, 0xFF)) {
        return false;
    }

    // Desliga todos os drivers
    for (uint8_t i = 0; i < 8; i++) {
        sendByte(SI5351_REG_16_CLK0_CTRL + i, 0x80); // Bit 7 = Power Down
    }

    // Configura a carga do cristal (10pF)
    if (!sendByte(SI5351_REG_183_CRYSTAL_LOAD, 0b11000000)) { // 10pF
        return false;
    }

    // Define a frequência do PLLA para 900MHz (um bom valor fixo)
    if (!set_pll(900000000)) {
        return false;
    }

    // Reseta os PLLs
    return sendByte(SI5351_REG_177_PLL_RESET, 0xAC);
}

/**
 * @brief Configura o PLLA para uma frequência VCO (aqui fixo em 900MHz).
 */
bool Si5351::set_pll(unsigned long pll_freq) {
    // f_VCO = f_XTAL * (a + b/c)
    // Para PLLA = 900MHz, XTAL = 25MHz:
    // a = 36, b = 0, c = 1 (Modo Inteiro)
    //
    // P1 = 128 * 36 - 512 = 4096 (0x1000)
    // P2 = 0
    // P3 = 1 (0x000001)

    uint32_t p1 = 4096;
    uint32_t p2 = 0;
    uint32_t p3 = 1;

    // --- CORREÇÃO (da versão anterior): Escreve P1, P2, P3 nos registradores corretos ---
    // PLLA usa registradores 26-33
    
    // Escreve P3 (Registradores 26, 27, 31)
    if (!sendByte(SI5351_REG_26_MSNA_P1, (p3 >> 8) & 0xFF)) return false; // Reg 26: P3[15:8]
    if (!sendByte(SI5351_REG_27_MSNA_P2, p3 & 0xFF)) return false;       // Reg 27: P3[7:0]
    
    // Escreve P1 (Registradores 28, 29, 30)
    if (!sendByte(SI5351_REG_29_MSNA_P4, (p1 >> 8) & 0xFF)) return false; // Reg 29: P1[15:8]
    if (!sendByte(SI5351_REG_30_MSNA_P5, p1 & 0xFF)) return false;       // Reg 30: P1[7:0]

    // Escreve P2 (Registradores 31, 32, 33)
    if (!sendByte(SI5351_REG_32_MSNA_P7, (p2 >> 8) & 0xFF)) return false; // Reg 32: P2[15:8]
    if (!sendByte(SI5351_REG_33_MSNA_P8, p2 & 0xFF)) return false;       // Reg 33: P2[7:0]

    // Escreve os bits MSB (mais significativos) que são misturados
    // Reg 28: P1[17:16]
    uint8_t p1_msb = (p1 >> 16) & 0x03;
    if (!sendByte(SI5351_REG_28_MSNA_P3, p1_msb)) return false; 

    // Reg 31: P3[19:16] | P2[19:16]
    uint8_t p3_p2_mix = ((p3 >> 16) & 0x0F) | ((p2 >> 16) & 0x0F) << 4;
    if (!sendByte(SI5351_REG_31_MSNA_P6, p3_p2_mix)) return false;
    
    return true;
}

/**
 * @brief Configura o MultiSynth (MS) para gerar a frequência de saída.
 */
bool Si5351::set_ms(uint8_t output_num, unsigned long pll_freq, unsigned long output_freq) {
    if (output_num > 7) return false;
    
    // f_OUT = f_VCO / (a * R_DIV)
    
    uint32_t a;
    uint32_t p1, p2, p3;
    uint8_t r_div = 0; // O código do R_DIV (0=1, 1=2, 2=4, ... 7=128)

    // --- LÓGICA DE DIVISÃO CORRIGIDA ---
    // 1. Encontra o R_DIV necessário para que 'a' (divisor do MultiSynth)
    //    fique dentro da faixa válida [4, 2048].
    
    // Tenta 'a' com R_DIV = 1 (r_div = 0)
    a = pll_freq / output_freq;

    while (a > 2048 && r_div < 7) {
        r_div++; // Aumenta o divisor R (1=2, 2=4, 3=8...)
        // Recalcula 'a' com o novo R_DIV
        // R_DIV_VAL = 1 << r_div (ou pow(2, r_div))
        a = pll_freq / (output_freq * (1 << r_div));
    }

    // 2. Verifica se o valor final de 'a' é válido
    if (a < 4 || a > 2048) {
        return false; // Frequência inválida (muito alta ou muito baixa)
    }
    // --- FIM DA LÓGICA DE DIVISÃO ---

    // Modo Inteiro (b=0, c=1)
    p1 = 128 * a - 512;
    p2 = 0;
    p3 = 1;

    // Encontra o registrador base para este MultiSynth (MS0, MS1, etc.)
    uint8_t ms_p1_reg = SI5351_REG_45_MS0_P4 + (output_num * 8); // Base P1 (Reg 45)
    uint8_t ms_p2_reg = SI5351_REG_48_MS0_P7 + (output_num * 8); // Base P2 (Reg 48)
    uint8_t ms_p3_reg = SI5351_REG_42_MS0_P1 + (output_num * 8); // Base P3 (Reg 42)
    uint8_t ms_r_reg = SI5351_REG_44_MS0_P3 + (output_num * 8); // Base R_DIV (Reg 44)
    uint8_t ms_mix_reg = SI5351_REG_47_MS0_P6 + (output_num * 8); // Base MIX (Reg 47)
    
    // Escreve P3 (Registradores 42, 43, 47)
    if (!sendByte(ms_p3_reg + 0, (p3 >> 8) & 0xFF)) return false; // Reg 42: P3[15:8]
    if (!sendByte(ms_p3_reg + 1, p3 & 0xFF)) return false;       // Reg 43: P3[7:0]

    // Escreve P1 (Registradores 44, 45, 46)
    if (!sendByte(ms_p1_reg + 0, (p1 >> 8) & 0xFF)) return false; // Reg 45: P1[15:8]
    if (!sendByte(ms_p1_reg + 1, p1 & 0xFF)) return false;       // Reg 46: P1[7:0]

    // Escreve P2 (Registradores 47, 48, 49)
    if (!sendByte(ms_p2_reg + 0, (p2 >> 8) & 0xFF)) return false; // Reg 48: P2[15:8]
    if (!sendByte(ms_p2_reg + 1, p2 & 0xFF)) return false;       // Reg 49: P2[7:0]

    // Escreve os bits MSB (mais significativos) misturados
    // Reg 44: R_DIV[2:0] | P1[17:16]
    uint8_t r_div_val = (r_div << 4) & 0xF0; // Usa o r_div calculado
    uint8_t p1_msb = (p1 >> 16) & 0x03;
    if (!sendByte(ms_r_reg, r_div_val | p1_msb)) return false; 
    
    // Reg 47: P3[19:16] | P2[19:16]
    uint8_t p3_p2_mix = ((p3 >> 16) & 0x0F) | ((p2 >> 16) & 0x0F) << 4;
    if (!sendByte(ms_mix_reg, p3_p2_mix)) return false;

    // Configura o CLK Control (Reg 16-23)
    uint8_t clk_ctrl_reg = SI5351_REG_16_CLK0_CTRL + output_num;
    
    // O valor correto é 0x4F (01001111)
    // Bit 6: 1 (MS_INT = Modo Inteiro)
    // Bit 5: 0 (MS_SRC = PLLA)
    // Bits 3:2: 11 (CLK_SRC = MultiSynth)
    // Bits 1:0: 11 (Drive = 8mA)
    uint8_t ctrl_val = 0x4F; 
    
    return sendByte(clk_ctrl_reg, ctrl_val);
}

/**
 * @brief Configura a frequência de saída (função principal).
 */
bool Si5351::set_freq(uint8_t output_num, unsigned long frequency) {
    // Nossa implementação usa PLLA fixo em 900MHz.
    unsigned long pll_freq = 900000000;
    
    // Configura o MultiSynth (MS) para a saída desejada
    if (!set_ms(output_num, pll_freq, frequency)) {
        return false;
    }
    
    // Reseta o PLL para aplicar as mudanças
    return sendByte(SI5351_REG_177_PLL_RESET, 0xAC);
}

/**
 * @brief Habilita ou desabilita uma saída de clock.
 */
bool Si5351::enable_output(uint8_t output_num, bool enable) {
    if (output_num > 7) return false;
    
    uint8_t reg_val;
    if (!readByte(SI5351_REG_3_OUTPUT_ENABLE, &reg_val)) {
        return false;
    }
    
    if (enable) {
        reg_val &= ~(1 << output_num); // 0 = Habilitado
    } else {
        reg_val |= (1 << output_num); // 1 = Desabilitado
    }
    
    return sendByte(SI5351_REG_3_OUTPUT_ENABLE, reg_val);
}