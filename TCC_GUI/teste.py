import sys
import serial
import serial.tools.list_ports
import pyqtgraph as pg
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, 
                             QTextEdit, QLineEdit, QPushButton, QComboBox, 
                             QHBoxLayout, QLabel, QMessageBox, QSplitter, 
                             QTabWidget, QFormLayout, QGroupBox)
from PyQt6.QtCore import QThread, pyqtSignal, QObject, Qt

# --- ID de Hardware Exato da sua placa ---
# Vamos usar isso para encontrar a porta automaticamente
TARGET_HWID = "VID:PID=0483:374B"

# ---------------------------------------------------------------
# CLASSE DO "TRABALHADOR" SERIAL (v0.9 - Versão Final Corrigida)
# ---------------------------------------------------------------
class SerialWorker(QObject):
    data_received = pyqtSignal(str)
    finished = pyqtSignal()
    port_found = pyqtSignal(str, str) # Emite o nome da porta (ex: COM5) e a descrição
    port_error = pyqtSignal(str)      # Emite erros

    def __init__(self, baudrate):
        super().__init__()
        self.port = None
        self.baudrate = baudrate
        self.running = True
        self.ser = None

    def find_port(self):
        """Procura pela porta usando o Hardware ID."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if TARGET_HWID in port.hwid:
                self.port = port.device
                self.port_found.emit(port.device, port.description)
                return
        self.port_error.emit("Porta ST-Link (0483:374B) nao encontrada.")

    def run(self):
        """A função principal do thread."""
        if self.port is None:
            self.port_error.emit("Nenhuma porta selecionada para conexao.")
            self.finished.emit()
            return
            
        try:
            # --- CORREÇÃO (v0.9) ---
            # 1. Cria o objeto serial SEM abrir
            self.ser = serial.Serial()
            self.ser.port = self.port
            self.ser.baudrate = self.baudrate
            self.ser.timeout = 1
            # 2. Define DTR/RTS para False ANTES de abrir
            self.ser.dtr = False
            self.ser.rts = False
            # 3. Abre a porta
            self.ser.open()
            # --- FIM DA CORREÇÃO ---
            
            self.data_received.emit(f"Conectado com sucesso em {self.port}.\r\n")
        except serial.SerialException as e:
            self.data_received.emit(f"Erro ao conectar: {e}\r\n")
            self.finished.emit()
            return

        # Lógica de leitura (usando readline(), que provamos funcionar)
        while self.running and self.ser:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if line:
                    self.data_received.emit(line) # Emite a linha limpa
            except serial.SerialException:
                self.data_received.emit("Erro de serial. Desconectado.\r\n")
                self.running = False
            except Exception as e:
                pass # Ignora erros de decodificação
        
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.finished.emit()

    def send_command(self, command):
        """Envia um comando pela serial."""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((command + '\n').encode('utf-8'))
            except serial.SerialException as e:
                self.data_received.emit(f"Erro ao enviar: {e}\r\n")

    def stop(self):
        """Para o thread."""
        self.running = False

# ---------------------------------------------------------------
# CLASSE DA JANELA PRINCIPAL (GUI v0.9)
# ---------------------------------------------------------------
class MainWindow(QMainWindow):
    command_to_worker = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analisador de Impedância v0.9 (Final)")
        self.setGeometry(100, 100, 800, 700)

        self.freq_data = []
        self.imp_data = []
        self.phase_data = []

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # 1. Seção de Conexão
        connection_layout = QHBoxLayout()
        self.port_label = QLabel("Porta COM:")
        self.port_combo = QComboBox()
        self.connect_button = QPushButton("Conectar")
        self.clear_button = QPushButton("Limpar Gráficos")
        connection_layout.addWidget(self.port_label)
        connection_layout.addWidget(self.port_combo, 1) # Expande o combobox
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.clear_button)
        self.layout.addLayout(connection_layout)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # --- Aba 1: Varredura (Gráficos e Ações) ---
        self.tab_sweep = QWidget()
        self.tabs.addTab(self.tab_sweep, "Varredura")
        self.sweep_layout = QVBoxLayout(self.tab_sweep)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.graph_container = QWidget()
        self.graph_layout = QVBoxLayout(self.graph_container)
        
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self.plot_widget_imp = pg.PlotWidget(title="Impedância (|Z|)")
        self.plot_widget_imp.setLabel('left', 'Impedância (Ohm)')
        self.plot_widget_imp.setLabel('bottom', 'Frequência (Hz)')
        self.plot_widget_imp.setLogMode(x=True, y=True)
        self.plot_widget_imp.showGrid(x=True, y=True)
        self.plot_data_imp = self.plot_widget_imp.plot(pen='b', symbol='o', symbolBrush='b', symbolSize=5)
        
        self.plot_widget_phase = pg.PlotWidget(title="Fase")
        self.plot_widget_phase.setLabel('left', 'Fase (deg)')
        self.plot_widget_phase.setLabel('bottom', 'Frequência (Hz)')
        self.plot_widget_phase.setLogMode(x=True, y=False)
        self.plot_widget_phase.showGrid(x=True, y=True)
        self.plot_data_phase = self.plot_widget_phase.plot(pen='r', symbol='o', symbolBrush='r', symbolSize=5)
        
        self.plot_widget_phase.setXLink(self.plot_widget_imp)
        self.graph_layout.addWidget(self.plot_widget_imp)
        self.graph_layout.addWidget(self.plot_widget_phase)
        self.splitter.addWidget(self.graph_container)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.splitter.addWidget(self.log_text)
        self.splitter.setSizes([400, 200])
        self.sweep_layout.addWidget(self.splitter)
        
        action_layout = QHBoxLayout()
        self.btn_calibrate = QPushButton("1. CALIBRAR")
        self.btn_sweep = QPushButton("2. VARREDURA (SWEEP)")
        action_layout.addWidget(self.btn_calibrate)
        action_layout.addWidget(self.btn_sweep)
        self.sweep_layout.addLayout(action_layout)

        # --- Aba 2: Configuração (Parâmetros) ---
        self.tab_config = QWidget()
        self.tabs.addTab(self.tab_config, "Configuração")
        self.config_layout = QVBoxLayout(self.tab_config)

        sweep_config_group = QGroupBox("Parâmetros da Varredura")
        sweep_form_layout = QFormLayout()
        self.le_start_freq = QLineEdit("1000")
        self.le_freq_incr = QLineEdit("1000")
        self.le_num_incr = QLineEdit("99")
        self.le_ref_resist = QLineEdit("1000")
        self.btn_apply_sweep_config = QPushButton("Aplicar Configurações de Varredura (setconfig)")
        sweep_form_layout.addRow("Freq. Inicial (Hz):", self.le_start_freq)
        sweep_form_layout.addRow("Incremento (Hz):", self.le_freq_incr)
        sweep_form_layout.addRow("Num. Pontos (N-1):", self.le_num_incr)
        sweep_form_layout.addRow("Resistor Ref. (Ohm):", self.le_ref_resist)
        sweep_form_layout.addRow(self.btn_apply_sweep_config)
        sweep_config_group.setLayout(sweep_form_layout)
        self.config_layout.addWidget(sweep_config_group)

        hw_config_group = QGroupBox("Parâmetros de Hardware (I2C)")
        hw_form_layout = QFormLayout()
        self.le_pot = QLineEdit("190")
        self.le_dac = QLineEdit("2048")
        self.le_mux1 = QLineEdit("4")
        self.le_mux2 = QLineEdit("5")
        self.btn_apply_hw_config = QPushButton("Aplicar Configurações de Hardware (Individual)")
        hw_form_layout.addRow("Potenciômetro (0-255):", self.le_pot)
        hw_form_layout.addRow("DAC (0-4095):", self.le_dac)
        hw_form_layout.addRow("MUX 1 (Porta 0-8):", self.le_mux1)
        hw_form_layout.addRow("MUX 2 (Porta 0-8):", self.le_mux2)
        hw_form_layout.addRow(self.btn_apply_hw_config)
        hw_config_group.setLayout(hw_form_layout)
        self.config_layout.addWidget(hw_config_group)
        
        self.config_layout.addStretch()
        self.tabs.setEnabled(False)

        self.serial_thread = None
        self.serial_worker = None

        self.populate_ports()
        self.connect_button.clicked.connect(self.toggle_connection)
        self.clear_button.clicked.connect(self.clear_plots)
        self.btn_calibrate.clicked.connect(self.run_calibrate)
        self.btn_sweep.clicked.connect(self.run_sweep)
        self.btn_apply_sweep_config.clicked.connect(self.apply_sweep_config)
        self.btn_apply_hw_config.clicked.connect(self.apply_hw_config)

    def populate_ports(self):
        """Procura e seleciona a porta ST-Link automaticamente."""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        found = False
        for port in sorted(ports):
            self.port_combo.addItem(f"{port.device} - {port.description}")
            if TARGET_HWID in port.hwid:
                self.port_combo.setCurrentText(f"{port.device} - {port.description}")
                found = True
        
        if not ports:
            self.port_combo.addItem("Nenhuma porta encontrada")
            self.connect_button.setEnabled(False)

    def toggle_connection(self):
        if self.serial_thread is None or not self.serial_thread.isRunning():
            port_full_name = self.port_combo.currentText()
            port_name = port_full_name.split(' - ')[0]
            if not port_name or "Nenhuma" in port_name:
                QMessageBox.critical(self, "Erro", "Nenhuma porta selecionada.")
                return

            self.log_text.append(f"Tentando conectar em {port_name}...")
            
            self.serial_thread = QThread()
            # Passa apenas o baudrate, a porta é encontrada no thread
            self.serial_worker = SerialWorker(115200)
            self.serial_worker.moveToThread(self.serial_thread)
            
            # Conecta os sinais ANTES de iniciar o thread
            self.serial_thread.started.connect(self.serial_worker.find_port) # 1. Encontra a porta
            self.serial_worker.port_found.connect(self.serial_worker.run)    # 2. Se encontrar, roda
            self.serial_worker.port_error.connect(self.handle_port_error)    # x. Se falhar, avisa
            
            self.serial_worker.data_received.connect(self.handle_serial_data)
            self.command_to_worker.connect(self.serial_worker.send_command)
            self.serial_worker.finished.connect(self.serial_thread.quit)
            self.serial_worker.finished.connect(self.serial_worker.deleteLater)
            self.serial_thread.finished.connect(self.serial_thread.deleteLater)
            self.serial_thread.finished.connect(self.thread_finished)
            
            self.serial_thread.start()
            
            self.connect_button.setText("Desconectar")
            self.port_combo.setEnabled(False)
            self.tabs.setEnabled(True)

        else:
            self.log_text.append("Desconectando...")
            if self.serial_worker: self.serial_worker.stop()
            if self.serial_thread: self.serial_thread.quit(); self.serial_thread.wait(1000)

    def handle_port_error(self, error_msg):
        """Recebe erro do thread e mostra na GUI."""
        self.log_text.append(f"ERRO: {error_msg}")
        self.thread_finished() # Reseta a GUI

    def send_command_to_stm(self, command):
        """Função central para enviar comandos e logar"""
        if self.serial_thread and self.serial_thread.isRunning():
            self.command_to_worker.emit(command)
            self.log_text.append(f">> {command}")
        else:
            self.log_text.append("ERRO: Não conectado.")

    def run_calibrate(self):
        self.clear_plots()
        self.send_command_to_stm("calibrate")

    def run_sweep(self):
        self.clear_plots()
        self.send_command_to_stm("sweep")

    def apply_sweep_config(self):
        """Lê os 4 campos de varredura e envia o comando 'setconfig'"""
        try:
            sfreq = int(self.le_start_freq.text())
            fincr = int(self.le_freq_incr.text())
            nincr = int(self.le_num_incr.text())
            rref = int(self.le_ref_resist.text())
            
            command = f"setconfig,{sfreq},{fincr},{nincr},{rref}"
            self.send_command_to_stm(command)
        except ValueError:
            self.log_text.append("ERRO: Todos os campos de varredura devem ser números inteiros.")

    def apply_hw_config(self):
        """Lê os 4 campos de hardware e envia os comandos individuais"""
        try:
            self.send_command_to_stm(f"pot,{int(self.le_pot.text())}")
            self.send_command_to_stm(f"dac,{int(self.le_dac.text())}")
            self.send_command_to_stm(f"mux1,{int(self.le_mux1.text())}")
            self.send_command_to_stm(f"mux2,{int(self.le_mux2.text())}")
        except ValueError:
            self.log_text.append("ERRO: Todos os campos de hardware devem ser números inteiros.")

    def handle_serial_data(self, data_string):
        self.log_text.append(data_string) 
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        if data_string.startswith("Freq:"):
            self.parse_and_plot(data_string)

    def parse_and_plot(self, data_string):
        try:
            parts = data_string.split('|')
            freq = float(parts[0].split(':')[1].split('Hz')[0].strip())
            imp = float(parts[3].split(':')[1].split('Ohm')[0].strip())
            phase = float(parts[4].split(':')[1].split('deg')[0].strip())

            self.freq_data.append(freq)
            self.imp_data.append(imp)
            self.phase_data.append(phase)
            
            self.plot_data_imp.setData(self.freq_data, self.imp_data)
            self.plot_data_phase.setData(self.freq_data, self.phase_data)
        except Exception as e:
            self.log_text.append(f"!! Erro ao processar dados: {e}")
            self.log_text.append(f"!! Linha com erro: {data_string}")

    def clear_plots(self):
        self.freq_data = []
        self.imp_data = []
        self.phase_data = []
        self.plot_data_imp.setData([], [])
        self.plot_data_phase.setData([], [])
        self.log_text.append("--- Gráficos limpos ---")

    def thread_finished(self):
        self.log_text.append("Conexão encerrada.")
        self.serial_thread = None
        self.serial_worker = None
        self.connect_button.setText("Conectar")
        self.port_combo.setEnabled(True)
        self.tabs.setEnabled(False)
        self.populate_ports() # Atualiza a lista de portas

    def closeEvent(self, event):
        if self.serial_thread and self.serial_thread.isRunning():
            self.serial_worker.stop()
            self.serial_thread.quit()
            self.serial_thread.wait(1000)
        event.accept()

# ---------------------------------------------------------------
# EXECUÇÃO DA APLICAÇÃO
# ---------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())