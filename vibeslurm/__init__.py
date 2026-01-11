"""vibeslurm - A GUI application for monitoring SLURM jobs."""

__version__ = "0.1.0"

from vibeslurm.slurm import SlurmCommands, SlurmError
from vibeslurm.gui import MainWindow

__all__ = ["__version__", "SlurmCommands", "SlurmError", "MainWindow"]
