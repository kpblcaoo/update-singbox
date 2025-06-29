"""Environment and service mode detection utilities.

Implements CONFIG-02 from ADR-0009: Hybrid auto-detection for service mode.
Provides reliable detection of systemd, container, and service environments.
"""

import os
import sys
from pathlib import Path


def detect_service_mode() -> bool:
    """Detect if application should run in service mode.
    
    Uses hybrid auto-detection strategy from ADR-0009 CONFIG-02:
    1. Explicit CLI flags (--service, --daemon)
    2. Environment detection (INVOCATION_ID for systemd)
    3. Process detection (parent process analysis)
    4. Container detection (Docker, Kubernetes, Podman)
    5. Default to CLI mode if uncertain
    
    Returns:
        bool: True if service mode should be enabled
    """
    # 1. Explicit override via CLI arguments
    if "--service" in sys.argv or "--daemon" in sys.argv:
        return True
    
    # Also check for explicit CLI mode override
    if "--cli" in sys.argv or "--interactive" in sys.argv:
        return False
    
    # 2. Systemd service detection
    if os.getenv("INVOCATION_ID"):
        return True
    
    # Additional systemd indicators
    if os.getenv("SYSTEMD_EXEC_PID"):
        return True
    
    # Check if running under systemd (systemd sets this)
    if os.path.exists("/run/systemd/system") and os.getenv("USER") != "root":
        # Likely a systemd user service
        return True
    
    # 3. Container environment detection
    if detect_container_environment():
        return True
    
    # 4. Process analysis - check if parent is systemd or init
    try:
        parent_pid = os.getppid()
        if parent_pid == 1:  # Direct child of init/systemd
            return True
        
        # Check parent process name
        parent_cmdline_path = f"/proc/{parent_pid}/cmdline"
        if os.path.exists(parent_cmdline_path):
            with open(parent_cmdline_path, 'r') as f:
                parent_cmd = f.read().strip('\x00')
                if 'systemd' in parent_cmd or parent_cmd.endswith('init'):
                    return True
    except (OSError, IOError):
        # Can't determine parent process, continue with other checks
        pass
    
    # 5. Environment variable override
    service_mode_env = os.getenv("SBOXMGR_SERVICE_MODE", "").lower()
    if service_mode_env in ("true", "1", "yes", "on"):
        return True
    elif service_mode_env in ("false", "0", "no", "off"):
        return False
    
    # 6. Default to CLI mode
    return False


def detect_container_environment() -> bool:
    """Detect if running in a container environment.
    
    Checks for various container indicators:
    - Docker (/.dockerenv file)
    - Kubernetes (KUBERNETES_SERVICE_HOST env var)
    - Podman (CONTAINER env var)
    - Generic container indicators
    
    Returns:
        bool: True if container environment detected
    """
    # Docker detection
    if os.path.exists("/.dockerenv"):
        return True
    
    # Kubernetes detection
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        return True
    
    # Podman detection
    if os.getenv("CONTAINER") == "podman":
        return True
    
    # Generic container detection via cgroups
    try:
        with open("/proc/1/cgroup", "r") as f:
            cgroup_content = f.read()
            if "docker" in cgroup_content or "containerd" in cgroup_content:
                return True
    except (OSError, IOError):
        pass
    
    # Check for container-specific mount points
    container_indicators = [
        "/proc/1/environ",  # Check init process environment
    ]
    
    for indicator_path in container_indicators:
        try:
            if os.path.exists(indicator_path):
                with open(indicator_path, "rb") as f:
                    environ_data = f.read().decode("utf-8", errors="ignore")
                    if "container" in environ_data.lower():
                        return True
        except (OSError, IOError):
            continue
    
    return False


def detect_systemd_environment() -> bool:
    """Detect if systemd is available and active.
    
    Checks for systemd availability for logging sink selection.
    Used by logging configuration to determine if journald is available.
    
    Returns:
        bool: True if systemd environment is detected
    """
    # Check for systemd runtime directory
    if os.path.exists("/run/systemd/system"):
        return True
    
    # Check for systemd in process tree
    if os.getenv("INVOCATION_ID") or os.getenv("SYSTEMD_EXEC_PID"):
        return True
    
    # Check if systemctl is available and working
    try:
        import subprocess
        result = subprocess.run(
            ["systemctl", "--version"],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_development_environment() -> bool:
    """Detect if running in development environment.
    
    Useful for setting development-friendly defaults.
    
    Returns:
        bool: True if development environment detected
    """
    # Check for common development indicators
    dev_indicators = [
        "VIRTUAL_ENV",  # Python virtual environment
        "CONDA_DEFAULT_ENV",  # Conda environment
        "PIPENV_ACTIVE",  # Pipenv environment
        "POETRY_ACTIVE",  # Poetry environment
    ]
    
    for indicator in dev_indicators:
        if os.getenv(indicator):
            return True
    
    # Check if running from source directory
    current_dir = Path.cwd()
    if (current_dir / "pyproject.toml").exists() or (current_dir / "setup.py").exists():
        return True
    
    # Check for development-specific files
    dev_files = [".git", ".vscode", ".idea", "Makefile", "tox.ini"]
    for dev_file in dev_files:
        if (current_dir / dev_file).exists():
            return True
    
    return False


def get_environment_info() -> dict:
    """Get comprehensive environment information for debugging.
    
    Returns:
        dict: Environment information including detection results
    """
    return {
        "service_mode": detect_service_mode(),
        "container_environment": detect_container_environment(),
        "systemd_environment": detect_systemd_environment(),
        "development_environment": detect_development_environment(),
        "environment_variables": {
            "INVOCATION_ID": os.getenv("INVOCATION_ID"),
            "SYSTEMD_EXEC_PID": os.getenv("SYSTEMD_EXEC_PID"),
            "KUBERNETES_SERVICE_HOST": os.getenv("KUBERNETES_SERVICE_HOST"),
            "CONTAINER": os.getenv("CONTAINER"),
            "VIRTUAL_ENV": os.getenv("VIRTUAL_ENV"),
            "SBOXMGR_SERVICE_MODE": os.getenv("SBOXMGR_SERVICE_MODE"),
        },
        "process_info": {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "cwd": str(Path.cwd()),
        },
        "file_indicators": {
            "/.dockerenv": os.path.exists("/.dockerenv"),
            "/run/systemd/system": os.path.exists("/run/systemd/system"),
            "/proc/1/cgroup": os.path.exists("/proc/1/cgroup"),
        }
    } 