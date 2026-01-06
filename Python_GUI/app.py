import sys
import re
import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLineEdit, QFormLayout, QGridLayout,
    QLabel, QTextBrowser, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
import pyqtgraph as pg

# --- CLASSE SerialWorker (Sem alterações) ---
class SerialWorker(QObject):
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error = pyqtSignal(str)
    data_received = pyqtSignal(str)

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.serial_connection = None
        self.running = False

    def connect(self):
        try:
            self.serial_connection = serial.Serial(
                self.port, self.baudrate, timeout=1
            )
            self.running = True
            self.connected.emit()
            self.read_loop()
        except serial.SerialException as e:
            self.error.emit(str(e))

    def read_loop(self):
        while self.running and self.serial_connection:
            try:
                if self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    if line:
                        self.data_received.emit(line)
            except serial.SerialException as e:
                self.error.emit(str(e))
                self.running = False
            except Exception as e:
                print(f"Erro de decodificação: {e}") 
                
        self.disconnect()

    def write(self, data):
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.write(data.encode('utf-8'))
            except serial.SerialException as e:
                self.error.emit(str(e))

    def disconnect(self):
        if self.serial_connection:
            self.running = False
            if self.serial_connection.is_open:
                self.serial_connection.close()
            self.serial_connection = None
        self.disconnected.emit()

# --- CLASSE MainWindow (Com adições) ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analisador de Impedância STM32")
        self.setGeometry(100, 100, 1200, 700)

        self.is_connected = False
        
        # --- Listas para a varredura ATUAL ---
        self.current_frequencies = []
        self.current_impedances = []
        self.current_phases = []
        
        # --- Referências para as curvas ATUAIS e ciclo de cores ---
        self.current_impedance_curve = None
        self.current_phase_curve = None
        
        self.plot_colors = ['y', 'c', 'm', 'r', 'g', 'b', (100, 100, 255), (255, 100, 100)] # Amarelo, Ciano, Magenta, Vermelho, Verde, Azul, etc
        self.color_index = 0
        
        self.serial_thread = None
        self.serial_worker = None

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- Painel de Controles (Esquerda) ---
        controls_layout = QVBoxLayout()
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 1. Conexão
        connection_layout = QGridLayout()
        self.cb_com_ports = QComboBox()
        self.btn_refresh_ports = QPushButton("Atualizar")
        self.btn_connect = QPushButton("Conectar")
        connection_layout.addWidget(QLabel("Porta COM:"), 0, 0)
        connection_layout.addWidget(self.cb_com_ports, 0, 1)
        connection_layout.addWidget(self.btn_refresh_ports, 0, 2)
        connection_layout.addWidget(self.btn_connect, 1, 0, 1, 3)
        controls_layout.addLayout(connection_layout)

        # 2. Configuração da Varredura
        config_layout = QFormLayout()
        self.le_start_freq = QLineEdit("1000")
        self.le_freq_incr = QLineEdit("1000")
        self.le_num_incr = QLineEdit("99")
        self.le_ref_resist = QLineEdit("1000")
        self.btn_send_config = QPushButton("Enviar Config")
        config_layout.addRow(QLabel("--- Configuração da Varredura ---"))
        config_layout.addRow("Freq. Inicial (Hz):", self.le_start_freq)
        config_layout.addRow("Incremento (Hz):", self.le_freq_incr)
        config_layout.addRow("Nº de Incrementos:", self.le_num_incr)
        config_layout.addRow("Resistor Ref. (Ohm):", self.le_ref_resist)
        config_layout.addRow(self.btn_send_config)
        controls_layout.addLayout(config_layout)

        # 3. Comandos de Ação
        commands_layout = QHBoxLayout()
        self.btn_calibrate = QPushButton("Calibrar")
        self.btn_sweep = QPushButton("Iniciar Varredura")
        self.btn_clear_plots = QPushButton("Limpar Gráficos")
        commands_layout.addWidget(self.btn_calibrate)
        commands_layout.addWidget(self.btn_sweep)
        commands_layout.addWidget(self.btn_clear_plots)
        controls_layout.addLayout(commands_layout)

        # 4. Configurações do Gráfico
        graph_settings_layout = QFormLayout()
        graph_settings_layout.addRow(QLabel("--- Configurações do Gráfico ---"))
        self.cb_log_scale = QCheckBox("Usar Escala Log (Impedância)")
        self.cb_log_scale.setChecked(True)
        graph_settings_layout.addRow(self.cb_log_scale)
        controls_layout.addLayout(graph_settings_layout)

        # 5. Controle Manual
        manual_control_layout = QFormLayout()
        manual_control_layout.addRow(QLabel("--- Controle Manual de Hardware ---"))
        self.le_dac_value = QLineEdit("2048")
        self.btn_send_dac = QPushButton("Enviar DAC")
        dac_layout = QHBoxLayout()
        dac_layout.addWidget(self.le_dac_value)
        dac_layout.addWidget(self.btn_send_dac)
        manual_control_layout.addRow("DAC (0-4095):", dac_layout)
        
        self.le_pot_value = QLineEdit("190")
        self.btn_send_pot = QPushButton("Enviar Pot.")
        pot_layout = QHBoxLayout()
        pot_layout.addWidget(self.le_pot_value)
        pot_layout.addWidget(self.btn_send_pot)
        manual_control_layout.addRow("Pot. (0-255):", pot_layout)
        
        self.le_mux1_port = QLineEdit("4")
        self.btn_send_mux1 = QPushButton("Enviar MUX 1")
        mux1_layout = QHBoxLayout()
        mux1_layout.addWidget(self.le_mux1_port)
        mux1_layout.addWidget(self.btn_send_mux1)
        manual_control_layout.addRow("MUX 1 (Porta 0-8):", mux1_layout)
        
        self.le_mux2_port = QLineEdit("5")
        self.btn_send_mux2 = QPushButton("Enviar MUX 2")
        mux2_layout = QHBoxLayout()
        mux2_layout.addWidget(self.le_mux2_port)
        mux2_layout.addWidget(self.btn_send_mux2)
        manual_control_layout.addRow("MUX 2 (Porta 0-8):", mux2_layout)

        # --- Bloco do MCLK Modificado ---
        self.le_mclk_value = QLineEdit("1,1000000") # Novo valor padrão
        self.btn_send_mclk = QPushButton("Enviar MCLK")
        mclk_layout = QHBoxLayout()
        mclk_layout.addWidget(self.le_mclk_value)
        mclk_layout.addWidget(self.btn_send_mclk)
        manual_control_layout.addRow("MCLK ([Pino],[Freq] ou 0):", mclk_layout) # Label atualizada
        # --- Fim do Bloco ---
        
        self.btn_get_status = QPushButton("Status AD5933")
        self.btn_reset_ad5933 = QPushButton("Reset AD5933")
        misc_layout = QHBoxLayout()
        misc_layout.addWidget(self.btn_get_status)
        misc_layout.addWidget(self.btn_reset_ad5933)
        manual_control_layout.addRow(misc_layout)
        controls_layout.addLayout(manual_control_layout)

        # 6. Console de Log
        controls_layout.addWidget(QLabel("--- Log do Dispositivo ---"))
        self.log_browser = QTextBrowser()
        controls_layout.addWidget(self.log_browser)
        main_layout.addLayout(controls_layout)

        # --- Painel de Gráficos (Direita) ---
        plots_layout = QVBoxLayout()
        
        self.plot_impedance = pg.PlotWidget()
        self.plot_impedance.setTitle("Impedância vs Frequência", size="16pt")
        self.plot_impedance.setLabel('left', "Impedância (Z)", units='Ohm')
        self.plot_impedance.setLabel('bottom', "Frequência (f)", units='Hz')
        self.plot_impedance.showGrid(x=True, y=True)
        self.plot_impedance.addLegend() 
        
        self.plot_phase = pg.PlotWidget()
        self.plot_phase.setTitle("Fase vs Frequência", size="16pt")
        self.plot_phase.setLabel('left', "Fase (Φ)", units='°')
        self.plot_phase.setLabel('bottom', "Frequência (f)", units='Hz')
        self.plot_phase.showGrid(x=True, y=True)
        self.plot_phase.getPlotItem().setYRange(-100, 100)
        self.plot_phase.addLegend() 
        self.plot_phase.setLogMode(x=False, y=False) 

        plots_layout.addWidget(self.plot_impedance)
        plots_layout.addWidget(self.plot_phase)
        main_layout.addLayout(plots_layout, stretch=2)

        # --- Conectar Sinais e Slots (Ações) ---
        self.btn_refresh_ports.clicked.connect(self.populate_com_ports)
        self.btn_connect.clicked.connect(self.toggle_connection)
        self.btn_send_config.clicked.connect(self.send_config)
        self.btn_calibrate.clicked.connect(self.start_calibrate)
        self.btn_sweep.clicked.connect(self.start_sweep)
        
        self.btn_send_dac.clicked.connect(self.send_dac)
        self.btn_send_pot.clicked.connect(self.send_pot)
        self.btn_send_mux1.clicked.connect(self.send_mux1)
        self.btn_send_mux2.clicked.connect(self.send_mux2)
        self.btn_get_status.clicked.connect(self.get_status)
        self.btn_reset_ad5933.clicked.connect(self.reset_ad5933)
        self.btn_send_mclk.clicked.connect(self.send_mclk)
        
        self.cb_log_scale.toggled.connect(self.toggle_impedance_log_scale)
        self.btn_clear_plots.clicked.connect(self.clear_plots)
        
        self.set_controls_enabled(False)
        self.toggle_impedance_log_scale(self.cb_log_scale.isChecked())

        self.populate_com_ports()

    def toggle_impedance_log_scale(self, is_checked):
        self.plot_impedance.setLogMode(x=False, y=is_checked) 
        log_state = "Logarítmica" if is_checked else "Linear"
        self.log_browser.append(f"[Gráfico] Eixo de Impedância alterado para escala {log_state}.")

    def get_next_color(self):
        color = self.plot_colors[self.color_index % len(self.plot_colors)]
        self.color_index += 1
        return color

    def clear_plots(self):
        self.plot_impedance.clear()
        self.plot_phase.clear()
        self.color_index = 0
        self.log_browser.append("[Gráfico] Gráficos limpos.")

    def populate_com_ports(self):
        self.cb_com_ports.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.cb_com_ports.addItem(f"{port.device} - {port.description}", port.device)
        self.log_browser.append("Portas COM atualizadas.")

    def toggle_connection(self):
        if not self.is_connected:
            port_name = self.cb_com_ports.currentData()
            if not port_name:
                self.log_browser.append("[ERRO] Nenhuma porta COM selecionada.")
                return

            self.log_browser.append(f"Tentando conectar em {port_name} a 115200 baud...")
            self.serial_thread = QThread()
            self.serial_worker = SerialWorker(port=port_name, baudrate=115200)
            self.serial_worker.moveToThread(self.serial_thread)
            self.serial_worker.connected.connect(self.on_connected)
            self.serial_worker.disconnected.connect(self.on_disconnected)
            self.serial_worker.error.connect(self.on_serial_error)
            self.serial_worker.data_received.connect(self.parse_serial_line)
            self.serial_thread.started.connect(self.serial_worker.connect)
            self.serial_thread.start()
        else:
            if self.serial_worker:
                self.serial_worker.disconnect()
            if self.serial_thread:
                self.serial_thread.quit()
                self.serial_thread.wait()
            self.on_disconnected()

    def set_controls_enabled(self, enabled):
        """ Habilita/Desabilita os botões de ação. """
        self.btn_send_config.setEnabled(enabled)
        self.btn_calibrate.setEnabled(enabled)
        self.btn_sweep.setEnabled(enabled)
        self.btn_clear_plots.setEnabled(enabled) 
        
        self.le_dac_value.setEnabled(enabled)
        self.btn_send_dac.setEnabled(enabled)
        self.le_pot_value.setEnabled(enabled)
        self.btn_send_pot.setEnabled(enabled)
        self.le_mux1_port.setEnabled(enabled)
        self.btn_send_mux1.setEnabled(enabled)
        self.le_mux2_port.setEnabled(enabled)
        self.btn_send_mux2.setEnabled(enabled)
        
        self.le_mclk_value.setEnabled(enabled) 
        self.btn_send_mclk.setEnabled(enabled) 
        
        self.btn_get_status.setEnabled(enabled)
        self.btn_reset_ad5933.setEnabled(enabled)
        
        self.cb_log_scale.setEnabled(enabled)

    def on_connected(self):
        self.log_browser.append("Conectado com sucesso!")
        self.is_connected = True
        self.btn_connect.setText("Desconectar")
        self.set_controls_enabled(True)
        self.cb_com_ports.setEnabled(False)
        self.btn_refresh_ports.setEnabled(False)

    def on_disconnected(self):
        self.log_browser.append("Desconectado.")
        self.is_connected = False
        self.btn_connect.setText("Conectar")
        self.set_controls_enabled(False)
        self.cb_com_ports.setEnabled(True)
        self.btn_refresh_ports.setEnabled(True)
        
        self.serial_thread = None
        self.serial_worker = None

    def on_serial_error(self, error_message):
        self.log_browser.append(f"[ERRO SERIAL] {error_message}")
        
        # Se estávamos conectados, o toggle_connection cuida da limpeza
        if self.is_connected:
            self.toggle_connection()
        else:
            # *** CORREÇÃO DO CRASH ***
            # Se a conexão falhou ANTES de self.is_connected = True,
            # (ou seja, falha imediata), precisamos limpar o thread manualmente.
            if self.serial_thread:
                self.serial_thread.quit()
                self.serial_thread.wait()
            # Agora podemos chamar on_disconnected com segurança
            self.on_disconnected()
            # *** FIM DA CORREÇÃO ***

    def send_simple_command(self, command, log_message):
        if not self.is_connected or not self.serial_worker:
            return
        self.log_browser.append(f"Enviando: {log_message}")
        self.serial_worker.write(f"{command}\n")

    def send_config(self):
        start_freq = self.le_start_freq.text()
        freq_incr = self.le_freq_incr.text()
        num_incr = self.le_num_incr.text()
        ref_resist = self.le_ref_resist.text()
        command = f"setconfig,{start_freq},{freq_incr},{num_incr},{ref_resist}"
        self.send_simple_command(command, command)

    def start_calibrate(self):
        self.send_simple_command("calibrate", "calibrate")

    def start_sweep(self):
        # 1. Limpa os dados da varredura ANTERIOR
        self.current_frequencies.clear()
        self.current_impedances.clear()
        self.current_phases.clear()
        
        # 2. Pega uma nova cor e cria novas curvas
        pen = self.get_next_color()
        sweep_name = f"Sweep {self.color_index}" # Para a legenda
        
        self.current_impedance_curve = self.plot_impedance.plot(
            pen=pen,
            symbol='o',
            symbolSize=5,
            name=sweep_name
        )
        self.current_phase_curve = self.plot_phase.plot(
            pen=pen,
            symbol='o',
            symbolSize=5,
            name=sweep_name
        )
        
        # 3. Envia o comando
        self.send_simple_command("sweep", "sweep")

    def send_dac(self):
        value = self.le_dac_value.text()
        self.send_simple_command(f"dac,{value}", f"dac,{value}")
        
    def send_pot(self):
        value = self.le_pot_value.text()
        self.send_simple_command(f"pot,{value}", f"pot,{value}")

    def send_mux1(self):
        port = self.le_mux1_port.text()
        self.send_simple_command(f"mux1,{port}", f"mux1,{port}")

    def send_mux2(self):
        port = self.le_mux2_port.text()
        self.send_simple_command(f"mux2,{port}", f"mux2,{port}")
        
    def get_status(self):
        self.send_simple_command("status", "status")

    def reset_ad5933(self):
        self.send_simple_command("reset", "reset")
        
    # --- Função Nova ---
    def send_mclk(self):
        value = self.le_mclk_value.text()
        # Envia o comando completo, ex: "setmclk,1,1000000" ou "setmclk,0"
        self.send_simple_command(f"setmclk,{value}", f"setmclk,{value}")

    def update_plots(self, freq, impedance, phase):
        # 1. Adiciona novos dados às listas temporárias
        self.current_frequencies.append(freq)
        self.current_impedances.append(impedance)
        self.current_phases.append(phase)
        
        # 2. Atualiza os dados das curvas ATUAIS (criadas em start_sweep)
        if self.current_impedance_curve:
            self.current_impedance_curve.setData(
                self.current_frequencies, self.current_impedances
            )
        if self.current_phase_curve:
            self.current_phase_curve.setData(
                self.current_frequencies, self.current_phases
            )
        
    def parse_serial_line(self, line):
    # 1. SEMPRE imprime a linha no log
        self.log_browser.append(f"STM32: {line}")

        # 2. Tenta fazer o parse da linha para o gráfico (sem o 'else')
        match = re.search(r"Freq: ([\d.]+) Hz .* Z: ([\d.]+) Ohm .* Fase: ([-\d.]+) deg", line)
        if match:
            try:
                freq = float(match.group(1))
                z = float(match.group(2))
                phase = float(match.group(3))
                self.update_plots(freq, z, phase) # Envia para o gráfico
            except ValueError:
                # Se falhar o parse, avisa no log
                self.log_browser.append(f"[Parse Error] Linha acima não é número flutuante.")

    def closeEvent(self, event):
        if self.is_connected:
            self.toggle_connection()
        event.accept()

# --- Ponto de Entrada da Aplicação ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())