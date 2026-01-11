"""Main entry point for vibeslurm."""

import sys
from qtpy.QtWidgets import QApplication
from vibeslurm.gui import MainWindow


def main():
    """Launch the vibeslurm application."""
    app = QApplication(sys.argv)
    app.setApplicationName("VibeSLURM")
    app.setOrganizationName("VibeSLURM")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
