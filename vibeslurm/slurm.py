"""SLURM command interface."""

import subprocess
from typing import Optional


class SlurmError(Exception):
    """Exception raised for SLURM command errors."""
    pass


class SlurmCommands:
    """Interface for executing SLURM commands."""

    @staticmethod
    def run_command(command: list[str]) -> tuple[str, str, int]:
        """
        Run a SLURM command and return output.

        Args:
            command: List of command arguments

        Returns:
            Tuple of (stdout, stderr, returncode)
        """
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            raise SlurmError(f"Command timed out: {' '.join(command)}")
        except FileNotFoundError:
            raise SlurmError(f"Command not found: {command[0]}")
        except Exception as e:
            raise SlurmError(f"Error running command: {e}")

    def squeue(self, user: Optional[str] = None, job_id: Optional[str] = None) -> str:
        """
        Run squeue command.

        Args:
            user: Filter by username
            job_id: Filter by job ID

        Returns:
            Command output
        """
        cmd = ["squeue"]
        if user:
            cmd.extend(["-u", user])
        if job_id:
            cmd.extend(["-j", job_id])

        stdout, stderr, returncode = self.run_command(cmd)
        if returncode != 0:
            raise SlurmError(f"squeue failed: {stderr}")
        return stdout

    def scancel(self, job_id: str) -> str:
        """
        Cancel a SLURM job.

        Args:
            job_id: Job ID to cancel

        Returns:
            Command output
        """
        cmd = ["scancel", job_id]
        stdout, stderr, returncode = self.run_command(cmd)
        if returncode != 0:
            raise SlurmError(f"scancel failed: {stderr}")
        return stdout or f"Job {job_id} cancelled successfully"

    def sbatch(self, script_path: str) -> str:
        """
        Submit a batch script.

        Args:
            script_path: Path to batch script

        Returns:
            Command output with job ID
        """
        cmd = ["sbatch", script_path]
        stdout, stderr, returncode = self.run_command(cmd)
        if returncode != 0:
            raise SlurmError(f"sbatch failed: {stderr}")
        return stdout

    def scontrol_show_job(self, job_id: str) -> str:
        """
        Show detailed job information.

        Args:
            job_id: Job ID to query

        Returns:
            Command output
        """
        cmd = ["scontrol", "show", "job", job_id]
        stdout, stderr, returncode = self.run_command(cmd)
        if returncode != 0:
            raise SlurmError(f"scontrol failed: {stderr}")
        return stdout
