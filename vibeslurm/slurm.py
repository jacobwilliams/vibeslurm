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

    def sinfo(self, partition: Optional[str] = None) -> str:
        """
        Run sinfo command to show cluster/partition information.

        Args:
            partition: Filter by partition name (optional)

        Returns:
            Command output
        """
        cmd = ["sinfo"]
        if partition:
            cmd.extend(["-p", partition])

        stdout, stderr, returncode = self.run_command(cmd)
        if returncode != 0:
            raise SlurmError(f"sinfo failed: {stderr}")
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

    def scancel_all(self, user: str) -> str:
        """
        Cancel all jobs for a user.

        Args:
            user: Username whose jobs to cancel

        Returns:
            Command output
        """
        cmd = ["scancel", "-u", user]
        stdout, stderr, returncode = self.run_command(cmd)
        if returncode != 0:
            raise SlurmError(f"scancel failed: {stderr}")
        return stdout or f"All jobs for user {user} cancelled successfully"

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

    def get_job_output_files(self, job_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        Get stdout and stderr file paths for a job.

        Args:
            job_id: Job ID to query

        Returns:
            Tuple of (stdout_path, stderr_path)
        """
        output = self.scontrol_show_job(job_id)
        stdout_path = None
        stderr_path = None

        for line in output.split('\n'):
            line = line.strip()
            if 'StdOut=' in line:
                parts = line.split('StdOut=')
                if len(parts) > 1:
                    stdout_path = parts[1].split()[0]
            if 'StdErr=' in line:
                parts = line.split('StdErr=')
                if len(parts) > 1:
                    stderr_path = parts[1].split()[0]

        return stdout_path, stderr_path

    def read_job_output(self, job_id: str, output_type: str = "stdout") -> str:
        """
        Read stdout or stderr file for a job.

        Args:
            job_id: Job ID to query
            output_type: Either 'stdout' or 'stderr'

        Returns:
            File contents
        """
        stdout_path, stderr_path = self.get_job_output_files(job_id)
        file_path = stdout_path if output_type == "stdout" else stderr_path

        if not file_path:
            raise SlurmError(f"No {output_type} file found for job {job_id}")

        try:
            with open(file_path, 'r') as f:
                content = f.read()
            return content if content else f"(Empty {output_type} file)"
        except FileNotFoundError:
            raise SlurmError(f"{output_type} file not found: {file_path}")
        except PermissionError:
            raise SlurmError(f"Permission denied reading {output_type} file: {file_path}")
        except Exception as e:
            raise SlurmError(f"Error reading {output_type} file: {e}")
