"""Main GUI window for vibeslurm."""

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
)
from qtpy.QtCore import Qt, QThread, Signal

from vibeslurm.slurm import SlurmCommands, SlurmError


class SlurmWorker(QThread):
    """Worker thread for running SLURM commands."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, command_func, *args, **kwargs):
        super().__init__()
        self.command_func = command_func
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
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("VibeSLURM - SLURM Job Monitor")
        self.setMinimumSize(800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # squeue section
        squeue_group = QGroupBox("Queue Status")
        squeue_layout = QVBoxLayout()

        squeue_controls = QHBoxLayout()
        self.user_input = QLineEdit()
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

        self.job_id_input = QLineEdit()
        self.job_id_input.setPlaceholderText("Job ID")
        control_layout.addWidget(QLabel("Job ID:"))
        control_layout.addWidget(self.job_id_input)

        self.cancel_btn = QPushButton("Cancel Job")
        self.cancel_btn.clicked.connect(self.on_scancel)
        control_layout.addWidget(self.cancel_btn)

        self.job_info_btn = QPushButton("Job Info")
        self.job_info_btn.clicked.connect(self.on_job_info)
        control_layout.addWidget(self.job_info_btn)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # Output display
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout()

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(300)
        output_layout.addWidget(self.output_text)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Status bar
        self.statusBar().showMessage("Ready")

    def run_slurm_command(self, command_func, *args, **kwargs):
        """Run a SLURM command in a worker thread."""
        if self.worker and self.worker.isRunning():
            self.output_text.append("⚠️ A command is already running...\n")
            return

        self.statusBar().showMessage("Running command...")
        self.worker = SlurmWorker(command_func, *args, **kwargs)
        self.worker.finished.connect(self.on_command_success)
        self.worker.error.connect(self.on_command_error)
        self.worker.start()

    def on_command_success(self, output: str):
        """Handle successful command execution."""
        self.output_text.append(output)
        self.output_text.append("\n" + "=" * 80 + "\n")
        self.statusBar().showMessage("Command completed successfully", 3000)

    def on_command_error(self, error: str):
        """Handle command execution error."""
        self.output_text.append(f"❌ Error: {error}\n")
        self.output_text.append("\n" + "=" * 80 + "\n")
        self.statusBar().showMessage("Command failed", 3000)
        QMessageBox.warning(self, "Error", error)

    def on_squeue(self):
        """Handle squeue button click."""
        user = self.user_input.text().strip() or None
        self.output_text.append(f"🔄 Running squeue{f' for user {user}' if user else ''}...\n")
        self.run_slurm_command(self.slurm.squeue, user=user)

    def on_scancel(self):
        """Handle scancel button click."""
        job_id = self.job_id_input.text().strip()
        if not job_id:
            QMessageBox.warning(self, "Input Error", "Please enter a Job ID")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Cancellation",
            f"Are you sure you want to cancel job {job_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.output_text.append(f"🛑 Cancelling job {job_id}...\n")
            self.run_slurm_command(self.slurm.scancel, job_id)

    def on_job_info(self):
        """Handle job info button click."""
        job_id = self.job_id_input.text().strip()
        if not job_id:
            QMessageBox.warning(self, "Input Error", "Please enter a Job ID")
            return

        self.output_text.append(f"ℹ️ Getting info for job {job_id}...\n")
        self.run_slurm_command(self.slurm.scontrol_show_job, job_id)
