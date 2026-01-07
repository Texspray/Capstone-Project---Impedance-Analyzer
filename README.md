# Portable Impedance Analyzer (Undergraduate Thesis)

![Status](https://img.shields.io/badge/Status-Completed-success)
![Language](https://img.shields.io/badge/C%2B%2B-Firmware-blue)
![Hardware](https://img.shields.io/badge/Hardware-Altium%20Designer-orange)

> **Repository for my Final Year Project (TCC) in Electronic Engineering.** [UPDATING]
> Design and implementation of a low-cost, portable impedance analyzer based on the AD5933 IC.

---

## 📸 Project Overview


Development of a custom instrumentation device capable of measuring complex impedance (magnitude and phase) across a frequency range. The system integrates an **AD5933 Impedance Converter Network Analyzer** with a microcontroller to perform frequency sweeps and process data.

### Key Features
* **Core Sensor:** Analog Devices AD5933 (1 MSPS, 12-bit ADC).
* **Microcontroller:** [STM32] for I2C control and data processing.
* **Frequency Range:** [1 kHz to 100 kHz].
* **User Interface:** [Python PC Interface].
* **Calibration:** Implements gain factor calibration for higher accuracy.

---

## 📂 Repository Structure

```text
├── Hardware/          # Altium Designer Project (Schematics, PCB, BOM)
├── Firmware/          # Source code (C/C++) for the Microcontroller
├── Python_GUI/        # (Optional) PC Interface for data visualization
├── Docs/              # Datasheets and Thesis PDF
└── Images/            # Images for this README
