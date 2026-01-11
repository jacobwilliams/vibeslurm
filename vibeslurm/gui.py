"""Main GUI window for vibeslurm."""

import getpass

from qtpy.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QLabel,
    QGroupBox,
    QMessageBox,
    QComboBox,
)
from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtGui import QFont

from vibeslurm.slurm import SlurmCommands, SlurmError


class SlurmWorker(QThread):
    """Worker thread for running SLURM commands."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, command_func, command_name, *args, **kwargs):
        super().__init__()
        self.command_func = command_func
        self.command_name = command_name
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """Execute the SLURM command."""
        try:
            result = self.command_func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except SlurmError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {str(e)}")


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.slurm = SlurmCommands()
        self.worker = None
        self.current_command = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("VibeSLURM - SLURM Job Monitor")
        self.setMinimumSize(600, 400)

        # Menu bar
        menubar = self.menuBar()
        view_menu = menubar.addMenu("View")
        clear_action = view_menu.addAction("Clear Output")
        clear_action.setShortcut("Ctrl+L")
        clear_action.triggered.connect(lambda: self.output_text.clear())

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # squeue section
        squeue_group = QGroupBox("Queue Status")
        squeue_layout = QVBoxLayout()

        squeue_controls = QHBoxLayout()
        self.user_input = QLineEdit()
        self.user_input.setText(getpass.getuser())
        self.user_input.setPlaceholderText("Username (optional)")
        squeue_controls.addWidget(QLabel("User:"))
        squeue_controls.addWidget(self.user_input)

        self.squeue_btn = QPushButton("Refresh Queue")
        self.squeue_btn.clicked.connect(self.on_squeue)
        squeue_controls.addWidget(self.squeue_btn)

        squeue_layout.addLayout(squeue_controls)
        squeue_group.setLayout(squeue_layout)
        layout.addWidget(squeue_group)

        # Job control section
        control_group = QGroupBox("Job Control")
        control_layout = QHBoxLayout()

        self.job_id_input = QComboBox()
        self.job_id_input.setEditable(True)
        self.job_id_input.setPlaceholderText("Job ID")
        control_layout.addWidget(QLabel("Job ID:"))
        control_layout.addWidget(self.job_id_input)

        self.cancel_btn = QPushButton("Cancel Job")
        self.cancel_btn.clicked.connect(self.on_scancel)
        control_layout.addWidget(self.cancel_btn)

        self.job_info_btn = QPushButton("Job Info")
        self.job_info_btn.clicked.connect(self.on_job_info)
        control_layout.addWidget(self.job_info_btn)

        self.cancel_all_btn = QPushButton("Cancel All Jobs")
        self.cancel_all_btn.clicked.connect(self.on_scancel_all)
        self.cancel_all_btn.setStyleSheet("background-color: #d9534f; color: white;")
        control_layout.addWidget(self.cancel_all_btn)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # Output display
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout()

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(100)
        self.output_text.setFont(QFont("Courier", 10))
        output_layout.addWidget(self.output_text)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Status bar
        self.statusBar().showMessage("Ready")

    def append_output(self, text: str):
        """Append text to output and scroll to bottom."""
        self.output_text.append(text)
        self.output_text.verticalScrollBar().setValue(self.output_text.verticalScrollBar().maximum())

    def run_slurm_command(self, command_name, command_func, *args, **kwargs):
        """Run a SLURM command in a worker thread."""
        if self.worker and self.worker.isRunning():
            self.append_output("⚠️ A command is already running...\n")
            return

        self.current_command = command_name
        self.statusBar().showMessage(f"Running: {command_name}")
        self.worker = SlurmWorker(command_func, command_name, *args, **kwargs)
        self.worker.finished.connect(self.on_command_success)
        self.worker.error.connect(self.on_command_error)
        self.worker.start()

    def on_command_success(self, output: str):
        """Handle successful command execution."""
        self.append_output(output)
        self.append_output("\n" + "─" * 40 + "\n")
        self.statusBar().showMessage("Command completed successfully", 3000)

        # If this was an squeue command, parse job IDs
        if self.current_command and self.current_command.startswith("squeue"):
            self.populate_job_ids(output)

    def populate_job_ids(self, squeue_output: str):
        """Parse squeue output and populate job ID dropdown."""
        self.job_id_input.clear()
        job_ids = []

        for line in squeue_output.strip().split("\n"):
            # Skip header line and empty lines
            if line.strip() and not line.strip().startswith("JOBID"):
                # Job ID is the first column
                parts = line.split()
                if parts:
                    job_id = parts[0].strip()
                    if job_id.isdigit():
                        job_ids.append(job_id)

        if job_ids:
            self.job_id_input.addItems(job_ids)
            self.statusBar().showMessage(f"Found {len(job_ids)} job(s)", 2000)

    def on_command_error(self, error: str):
        """Handle command execution error."""
        self.append_output(f"❌ Error: {error}\n")
        self.append_output("\n" + "─" * 40 + "\n")
        status_msg = f"Command failed: {self.current_command}" if self.current_command else "Command failed"
        self.statusBar().showMessage(status_msg, 5000)
        QMessageBox.warning(self, "Error", error)

    def on_squeue(self):
        """Handle squeue button click."""
        user = self.user_input.text().strip() or None
        cmd_name = f"squeue -u {user}" if user else "squeue"
        self.append_output(f"🔄 Running {cmd_name}...\n")
        self.run_slurm_command(cmd_name, self.slurm.squeue, user=user)

    def on_scancel(self):
        """Handle scancel button click."""
        job_id = self.job_id_input.currentText().strip()
        if not job_id:
            QMessageBox.warning(self, "Input Error", "Please enter or select a Job ID")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Cancellation",
            f"Are you sure you want to cancel job {job_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            cmd_name = f"scancel {job_id}"
            self.append_output(f"🛑 Cancelling job {job_id}...\n")
            self.run_slurm_command(cmd_name, self.slurm.scancel, job_id)

    def on_job_info(self):
        """Handle job info button click."""
        job_id = self.job_id_input.currentText().strip()
        if not job_id:
            QMessageBox.warning(self, "Input Error", "Please enter or select a Job ID")
            return

        self.append_output(f"ℹ️ Getting info for job {job_id}...\n")
        cmd_name = f"scontrol show job {job_id}"
        self.run_slurm_command(cmd_name, self.slurm.scontrol_show_job, job_id)

    def on_scancel_all(self):
        """Handle cancel all jobs button click."""
        user = self.user_input.text().strip()
        if not user:
            QMessageBox.warning(self, "Input Error", "Please enter a username")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Cancellation",
            f"Are you sure you want to cancel ALL jobs for user {user}?\n\nThis cannot be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            cmd_name = f"scancel -u {user}"
            self.append_output(f"🛑 Cancelling all jobs for user {user}...\n")
            self.run_slurm_command(cmd_name, self.slurm.scancel_all, user)
