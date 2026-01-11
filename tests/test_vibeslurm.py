"""Basic tests for vibeslurm package."""

import vibeslurm
from vibeslurm.slurm import SlurmCommands


def test_version():
    """Test that version is defined."""
    assert hasattr(vibeslurm, "__version__")
    assert isinstance(vibeslurm.__version__, str)


def test_slurm_commands_exists():
    """Test that SlurmCommands class can be instantiated."""
    slurm = SlurmCommands()
    assert slurm is not None
