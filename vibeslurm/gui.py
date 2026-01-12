"""Main GUI window for vibeslurm."""

import getpass
import os
from datetime import datetime

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
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QFileDialog,
    QDialog,
    QCheckBox,
)
from qtpy.QtCore import Qt, QThread, Signal, QTimer
from qtpy.QtGui import QColor, QFontDatabase

from .slurm import SlurmCommands, SlurmError


FONTSIZE = 12
AUTO_REFRESH_INTERVAL = 10000  # 10 seconds in milliseconds

class LogTailDialog(QDialog):
    """Dialog for tailing job output files in real-time."""

    def __init__(self, job_id: str, stdout_path: str, stderr_path: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path
        self.stdout_pos = 0
        self.stderr_pos = 0

        self.init_ui()

        # Set up timer to update logs
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_logs)
        self.timer.start(1000)  # Update every second

    def init_ui(self):
        """Initialize the dialog UI."""
        self.setWindowTitle(f"Live Logs - Job {self.job_id}")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)

        # StdOut section
        stdout_group = QGroupBox("Standard Output")
        stdout_layout = QVBoxLayout()

        stdout_path_label = QLabel(f"File: {self.stdout_path or 'Not available'}")
        stdout_path_label.setStyleSheet(F"font-size: {FONTSIZE}pt; color: gray;")
        stdout_layout.addWidget(stdout_path_label)

        self.stdout_mtime_label = QLabel("Last modified: N/A")
        self.stdout_mtime_label.setStyleSheet(F"font-size: {FONTSIZE}pt; color: gray;")
        stdout_layout.addWidget(self.stdout_mtime_label)

        self.stdout_text = QTextEdit()
        self.stdout_text.setReadOnly(True)
        stdout_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        stdout_font.setPointSize(FONTSIZE)
        self.stdout_text.setFont(stdout_font)
        self.stdout_text.setPlaceholderText("Waiting for output...")
        stdout_layout.addWidget(self.stdout_text)

        stdout_group.setLayout(stdout_layout)
        splitter.addWidget(stdout_group)

        # StdErr section
        stderr_group = QGroupBox("Standard Error")
        stderr_layout = QVBoxLayout()

        stderr_path_label = QLabel(f"File: {self.stderr_path or 'Not available'}")
        stderr_path_label.setStyleSheet(F"font-size: {FONTSIZE}pt; color: gray;")
        stderr_layout.addWidget(stderr_path_label)

        self.stderr_mtime_label = QLabel("Last modified: N/A")
        self.stderr_mtime_label.setStyleSheet(F"font-size: {FONTSIZE}pt; color: gray;")
        stderr_layout.addWidget(self.stderr_mtime_label)

        self.stderr_text = QTextEdit()
        self.stderr_text.setReadOnly(True)
        stderr_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        stderr_font.setPointSize(FONTSIZE)
        self.stderr_text.setFont(stderr_font)
        self.stderr_text.setPlaceholderText("Waiting for errors...")
        stderr_layout.addWidget(self.stderr_text)

        stderr_group.setLayout(stderr_layout)
        splitter.addWidget(stderr_group)

        # Set initial splitter sizes (50/50 split)
        splitter.setSizes([200, 200])

        layout.addWidget(splitter)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def update_logs(self):
        """Read new content from log files and update displays."""
        # Update stdout
        if self.stdout_path:
            try:
                # Update modification time
                mtime = os.path.getmtime(self.stdout_path)
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                self.stdout_mtime_label.setText(f"Last modified: {mtime_str}")

                with open(self.stdout_path, 'r') as f:
                    f.seek(self.stdout_pos)
                    new_content = f.read()
                    if new_content:
                        self.stdout_text.append(new_content.rstrip())
                        self.stdout_pos = f.tell()
                        # Auto-scroll to bottom
                        scrollbar = self.stdout_text.verticalScrollBar()
                        scrollbar.setValue(scrollbar.maximum())
            except FileNotFoundError:
                # File doesn't exist yet, that's okay
                pass
            except Exception as e:
                # Only show error once
                if self.stdout_pos == 0:
                    self.stdout_text.setPlaceholderText(f"Error reading file: {e}")

        # Update stderr
        if self.stderr_path:
            try:
                # Update modification time
                mtime = os.path.getmtime(self.stderr_path)
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                self.stderr_mtime_label.setText(f"Last modified: {mtime_str}")

                with open(self.stderr_path, 'r') as f:
                    f.seek(self.stderr_pos)
                    new_content = f.read()
                    if new_content:
                        self.stderr_text.append(new_content.rstrip())
                        self.stderr_pos = f.tell()
                        # Auto-scroll to bottom
                        scrollbar = self.stderr_text.verticalScrollBar()
                        scrollbar.setValue(scrollbar.maximum())
            except FileNotFoundError:
                # File doesn't exist yet, that's okay
                pass
            except Exception as e:
                # Only show error once
                if self.stderr_pos == 0:
                    self.stderr_text.setPlaceholderText(f"Error reading file: {e}")

    def closeEvent(self, event):
        """Clean up when dialog is closed."""
        self.timer.stop()
        super().closeEvent(event)


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

        # Set up auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.on_squeue)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("VibeSLURM - SLURM Job Monitor")
        self.setMinimumSize(600, 400)

        # Menu bar
        menubar = self.menuBar()

        # Job menu
        job_menu = menubar.addMenu("Job")
        submit_action = job_menu.addAction("Submit Job...")
        submit_action.setShortcut("Ctrl+S")
        submit_action.triggered.connect(self.on_submit_job)

        # Cluster menu
        cluster_menu = menubar.addMenu("Cluster")
        cluster_info_action = cluster_menu.addAction("View Cluster Info")
        cluster_info_action.setShortcut("Ctrl+I")
        cluster_info_action.triggered.connect(self.on_cluster_info)

        # View menu
        view_menu = menubar.addMenu("View")
        clear_action = view_menu.addAction("Clear Console")
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

        self.auto_refresh_checkbox = QCheckBox(f"Auto-refresh ({AUTO_REFRESH_INTERVAL // 1000}s)")
        self.auto_refresh_checkbox.stateChanged.connect(self.on_auto_refresh_toggle)
        squeue_controls.addWidget(self.auto_refresh_checkbox)

        squeue_layout.addLayout(squeue_controls)
        squeue_group.setLayout(squeue_layout)
        layout.addWidget(squeue_group)

        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)

        # Job info table
        table_group = QGroupBox("Job Information")
        table_layout = QVBoxLayout()

        self.job_table = QTableWidget()
        self.job_table.setColumnCount(8)
        self.job_table.setHorizontalHeaderLabels([
            "Job ID", "Partition", "Name", "User", "State", "Time", "Nodes", "Nodelist"
        ])
        self.job_table.horizontalHeader().setStretchLastSection(True)
        self.job_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.job_table.setAlternatingRowColors(True)
        self.job_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.job_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.job_table.setMinimumHeight(150)
        self.job_table.setSortingEnabled(True)  # Enable sorting by clicking headers
        self.job_table.itemDoubleClicked.connect(self.on_table_double_click)

        table_layout.addWidget(self.job_table)

        # Job control buttons
        buttons_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel Job")
        self.cancel_btn.clicked.connect(self.on_scancel)
        buttons_layout.addWidget(self.cancel_btn)

        self.job_info_btn = QPushButton("Job Info")
        self.job_info_btn.clicked.connect(self.on_job_info)
        buttons_layout.addWidget(self.job_info_btn)

        self.stdout_btn = QPushButton("View StdOut")
        self.stdout_btn.clicked.connect(self.on_view_stdout)
        buttons_layout.addWidget(self.stdout_btn)

        self.stderr_btn = QPushButton("View StdErr")
        self.stderr_btn.clicked.connect(self.on_view_stderr)
        buttons_layout.addWidget(self.stderr_btn)

        self.tail_logs_btn = QPushButton("Tail Logs")
        self.tail_logs_btn.clicked.connect(self.on_tail_logs)
        self.tail_logs_btn.setStyleSheet("background-color: #5bc0de; color: white;")
        buttons_layout.addWidget(self.tail_logs_btn)

        self.cancel_all_btn = QPushButton("Cancel All Jobs")
        self.cancel_all_btn.clicked.connect(self.on_scancel_all)
        self.cancel_all_btn.setStyleSheet("background-color: #d9534f; color: white;")
        buttons_layout.addWidget(self.cancel_all_btn)

        table_layout.addLayout(buttons_layout)

        table_group.setLayout(table_layout)
        splitter.addWidget(table_group)

        # Output display
        output_group = QGroupBox("Console")
        output_layout = QVBoxLayout()

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(100)
        output_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        output_font.setPointSize(FONTSIZE)
        self.output_text.setFont(output_font)
        output_layout.addWidget(self.output_text)

        output_group.setLayout(output_layout)
        splitter.addWidget(output_group)

        # Set initial splitter sizes (60% table, 40% output)
        splitter.setSizes([300, 200])

        layout.addWidget(splitter)

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

        # If this was a cancel command, refresh the queue
        elif self.current_command and self.current_command.startswith("scancel"):
            self.on_squeue()

        # If this was an sbatch command, refresh the queue
        elif self.current_command and self.current_command.startswith("sbatch"):
            self.on_squeue()

    def get_state_color(self, state: str) -> QColor:
        """Get color for a job state."""
        state_colors = {
            # Running states - green
            'R': QColor(144, 238, 144),  # Light green
            'RUNNING': QColor(144, 238, 144),

            # Pending states - yellow/orange
            'PD': QColor(255, 255, 153),  # Light yellow
            'PENDING': QColor(255, 255, 153),
            'CF': QColor(255, 229, 153),  # Light orange (configuring)
            'CONFIGURING': QColor(255, 229, 153),

            # Completing states - light blue
            'CG': QColor(173, 216, 230),  # Light blue
            'COMPLETING': QColor(173, 216, 230),

            # Completed - pale green
            'CD': QColor(200, 255, 200),
            'COMPLETED': QColor(200, 255, 200),

            # Failed/Error states - red/pink
            'F': QColor(255, 182, 193),  # Light pink
            'FAILED': QColor(255, 182, 193),
            'TO': QColor(255, 160, 160),  # Darker pink (timeout)
            'TIMEOUT': QColor(255, 160, 160),
            'NF': QColor(255, 160, 160),  # Node fail
            'NODE_FAIL': QColor(255, 160, 160),
            'OOM': QColor(255, 160, 160),  # Out of memory

            # Cancelled - gray
            'CA': QColor(211, 211, 211),  # Light gray
            'CANCELLED': QColor(211, 211, 211),

            # Suspended - lavender
            'S': QColor(216, 191, 216),
            'SUSPENDED': QColor(216, 191, 216),

            # Preempted - orange
            'PR': QColor(255, 200, 124),
            'PREEMPTED': QColor(255, 200, 124),
        }
        return state_colors.get(state, QColor(255, 255, 255))  # Default white

    def populate_job_ids(self, squeue_output: str):
        """Parse squeue output and populate job table."""
        self.job_table.setRowCount(0)
        job_count = 0

        lines = squeue_output.strip().split("\n")
        if not lines:
            return

        # Process each line
        for line in lines:
            line = line.strip()
            if not line or line.startswith("JOBID"):
                continue

            # Parse the line - typical squeue format:
            # JOBID PARTITION NAME USER ST TIME NODES NODELIST(REASON)
            parts = line.split()
            if len(parts) >= 8:
                job_id = parts[0]
                partition = parts[1]
                name = parts[2]
                user = parts[3]
                state = parts[4]
                time = parts[5]
                nodes = parts[6]
                nodelist = " ".join(parts[7:])  # Handle multi-word nodelist

                if job_id.isdigit():
                    job_count += 1

                    # Get color for this job state
                    state_color = self.get_state_color(state)

                    # Add to table
                    row = self.job_table.rowCount()
                    self.job_table.insertRow(row)

                    # Create items
                    items = [
                        QTableWidgetItem(job_id),
                        QTableWidgetItem(partition),
                        QTableWidgetItem(name),
                        QTableWidgetItem(user),
                        QTableWidgetItem(state),
                        QTableWidgetItem(time),
                        QTableWidgetItem(nodes),
                        QTableWidgetItem(nodelist),
                    ]

                    for col, item in enumerate(items):
                        # Only color the State column (index 4)
                        if col == 4:
                            item.setBackground(state_color)
                            item.setForeground(QColor(0, 0, 0))  # Black text
                        self.job_table.setItem(row, col, item)

        if job_count > 0:
            self.statusBar().showMessage(f"Found {job_count} job(s)", 2000)
            # Select the first row by default
            self.job_table.selectRow(0)

        # Auto-resize columns to content
        self.job_table.resizeColumnsToContents()

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

    def on_auto_refresh_toggle(self, state):
        """Handle auto-refresh checkbox toggle."""
        if self.auto_refresh_checkbox.isChecked():
            self.refresh_timer.start(AUTO_REFRESH_INTERVAL)
            self.statusBar().showMessage(f"Auto-refresh enabled ({AUTO_REFRESH_INTERVAL // 1000}s interval)", 2000)
            # Immediately refresh when enabled
            self.on_squeue()
        else:
            self.refresh_timer.stop()
            self.statusBar().showMessage("Auto-refresh disabled", 2000)

    def on_scancel(self):
        """Handle scancel button click."""
        selected_rows = self.job_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "Input Error", "Please select a job from the table")
            return

        row = selected_rows[0].row()
        job_id_item = self.job_table.item(row, 0)
        if not job_id_item:
            return

        job_id = job_id_item.text()

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
        selected_rows = self.job_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "Input Error", "Please select a job from the table")
            return

        row = selected_rows[0].row()
        job_id_item = self.job_table.item(row, 0)
        if not job_id_item:
            return

        job_id = job_id_item.text()

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

    def on_table_double_click(self, item):
        """Handle double-click on table row to show job info."""
        self.on_job_info()

    def on_view_stdout(self):
        """Handle view stdout button click."""
        selected_rows = self.job_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "Input Error", "Please select a job from the table")
            return

        row = selected_rows[0].row()
        job_id_item = self.job_table.item(row, 0)
        if not job_id_item:
            return

        job_id = job_id_item.text()

        self.append_output(f"📄 Reading stdout for job {job_id}...\n")
        cmd_name = f"cat stdout for job {job_id}"
        self.run_slurm_command(cmd_name, self.slurm.read_job_output, job_id, "stdout")

    def on_view_stderr(self):
        """Handle view stderr button click."""
        selected_rows = self.job_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "Input Error", "Please select a job from the table")
            return

        row = selected_rows[0].row()
        job_id_item = self.job_table.item(row, 0)
        if not job_id_item:
            return

        job_id = job_id_item.text()

        self.append_output(f"📄 Reading stderr for job {job_id}...\n")
        cmd_name = f"cat stderr for job {job_id}"
        self.run_slurm_command(cmd_name, self.slurm.read_job_output, job_id, "stderr")

    def on_submit_job(self):
        """Handle submit job menu action."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Batch Script to Submit",
            "",
            "Batch Scripts (*.sh *.slurm *.sbatch);;All Files (*)"
        )

        if file_path:
            reply = QMessageBox.question(
                self,
                "Confirm Submission",
                f"Submit batch script:\n{file_path}\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.append_output(f"📤 Submitting batch script: {file_path}...\n")
                cmd_name = f"sbatch {file_path}"
                self.run_slurm_command(cmd_name, self.slurm.sbatch, file_path)

    def on_cluster_info(self):
        """Handle cluster info menu action."""
        self.append_output("🖥️ Getting cluster information...\n")
        cmd_name = "sinfo"
        self.run_slurm_command(cmd_name, self.slurm.sinfo)

    def on_tail_logs(self):
        """Handle tail logs button click."""
        selected_rows = self.job_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "Input Error", "Please select a job from the table")
            return

        row = selected_rows[0].row()
        job_id_item = self.job_table.item(row, 0)
        if not job_id_item:
            return

        job_id = job_id_item.text()

        try:
            # Get output file paths
            stdout_path, stderr_path = self.slurm.get_job_output_files(job_id)

            # Create and show the tail dialog
            tail_dialog = LogTailDialog(job_id, stdout_path, stderr_path, self)
            tail_dialog.show()  # Use show() instead of exec() to allow multiple dialogs

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not get log files for job {job_id}:\n{str(e)}")
