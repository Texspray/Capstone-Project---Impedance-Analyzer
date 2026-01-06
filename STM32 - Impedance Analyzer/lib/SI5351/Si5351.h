#ifndef SI5351_H
#define SI5351_H

#include "stm32f4xx_hal.h"

// Endereço I2C padrão do Si5351
#define SI5351_ADDRESS (0x60 << 1) 

// Frequência do cristal (XTAL) do módulo Si5351 (geralmente 25MHz)
#define SI5351_XTAL_FREQ 25000000UL

// Registradores (baseado no datasheet)
#define SI5351_REG_0_DEVICE_STATUS 0
#define SI5351_REG_3_OUTPUT_ENABLE 3
#define SI5351_REG_15_PLL_INPUT_SRC 15
#define SI5351_REG_16_CLK0_CTRL 16
#define SI5351_REG_17_CLK1_CTRL 17
#define SI5351_REG_18_CLK2_CTRL 18
// ... (Registros 19-23 para CLK3-7 se necessário)
#define SI5351_REG_26_MSNA_P1 26 // Parâmetros do PLL A
#define SI5351_REG_27_MSNA_P2 27
#define SI5351_REG_28_MSNA_P3 28
#define SI5351_REG_29_MSNA_P4 29
#define SI5351_REG_30_MSNA_P5 30
#define SI5351_REG_31_MSNA_P6 31
#define SI5351_REG_32_MSNA_P7 32
#define SI5351_REG_33_MSNA_P8 33
#define SI5351_REG_42_MS0_P1 42 // Parâmetros do MultiSynth 0
#define SI5351_REG_43_MS0_P2 43
#define SI5351_REG_44_MS0_P3 44
#define SI5351_REG_45_MS0_P4 45
#define SI5351_REG_46_MS0_P5 46
#define SI5351_REG_47_MS0_P6 47
#define SI5351_REG_48_MS0_P7 48
#define SI5351_REG_49_MS0_P8 49
// ... (Registros 50-107 para MS1-7 se necessário)
#define SI5351_REG_177_PLL_RESET 177
#define SI5351_REG_183_CRYSTAL_LOAD 183


class Si5351 {
public:
    /**
     * @brief Inicializa o Si5351 e verifica a comunicação I2C.
     * @return true se o dispositivo foi encontrado, false caso contrário.
     */
    static bool init();

    /**
     * @brief Configura uma frequência de saída em um dos clocks.
     * Usa o PLLA (fixo em 900MHz) como fonte.
     * @param output_num O número da saída (0, 1 ou 2).
     * @param frequency A frequência de saída desejada em Hz.
     * @return true se sucesso, false se falha.
     */
    static bool set_freq(uint8_t output_num, unsigned long frequency);

    /**
     * @brief Habilita ou desabilita uma saída de clock.
     * @param output_num O número da saída (0-7).
     * @param enable true para ligar, false para desligar.
     * @return true se sucesso, false se falha.
     */
    static bool enable_output(uint8_t output_num, bool enable);

private:
    /**
     * @brief Escreve um byte em um registrador do Si5351.
     */
    static bool sendByte(uint8_t reg, uint8_t value);

    /**
     * @brief Lê um byte de um registrador do Si5351.
     */
    static bool readByte(uint8_t reg, uint8_t* value);

    /**
     * @brief Configura o PLLA ou PLLB para uma frequência VCO.
     * NOTA: Esta implementação simplificada SÓ configura o PLLA.
     */
    static bool set_pll(unsigned long pll_freq);

    /**
     * @brief Configura o MultiSynth (MS) para gerar a frequência de saída.
     */
    static bool set_ms(uint8_t output_num, unsigned long pll_freq, unsigned long output_freq);
};

#endif // SI5351_H