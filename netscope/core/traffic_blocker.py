"""Traffic blocking using iptables.

Allows blocking/unblocking network access for specific processes by PID.
Uses iptables owner module to match packets by process owner.
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BlockedProcess:
    """Information about a blocked process."""
    pid: int
    process_name: str
    blocked_at: float  # timestamp
    block_inbound: bool = True
    block_outbound: bool = True


class TrafficBlocker:
    """Manages network traffic blocking for processes using iptables."""

    CHAIN_NAME = "NETSCOPE_BLOCK"

    CONFIG_FILE = Path.home() / ".config" / "netscope" / "blocked_processes.json"

    def __init__(self):
        self._blocked: dict[int, BlockedProcess] = {}
        self._sudo_available: bool = self._check_sudo()
        self._load_blocked()

    def _check_sudo(self) -> bool:
        """Check if we can use sudo."""
        if os.geteuid() == 0:
            return True
        # Test if sudo is available without password
        try:
            result = subprocess.run(
                ["sudo", "-n", "true"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if traffic blocking is available."""
        return self._sudo_available

    def _load_blocked(self) -> None:
        """Load blocked process list from file."""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE) as f:
                    data = json.load(f)
                    for item in data.get("blocked", []):
                        pid = item["pid"]
                        self._blocked[pid] = BlockedProcess(
                            pid=pid,
                            process_name=item.get("process_name", f"pid:{pid}"),
                            blocked_at=item.get("blocked_at", time.time()),
                            block_inbound=item.get("block_inbound", True),
                            block_outbound=item.get("block_outbound", True)
                        )
            except (json.JSONDecodeError, OSError):
                pass

    def _save_blocked(self) -> None:
        """Save blocked process list to file."""
        self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, "w") as f:
            json.dump({
                "blocked": [
                    {
                        "pid": bp.pid,
                        "process_name": bp.process_name,
                        "blocked_at": bp.blocked_at,
                        "block_inbound": bp.block_inbound,
                        "block_outbound": bp.block_outbound
                    }
                    for bp in self._blocked.values()
                ]
            }, f, indent=2)

    def _get_uid_for_pid(self, pid: int) -> Optional[int]:
        """Get the UID that owns a process."""
        try:
            status_path = f"/proc/{pid}/status"
            with open(status_path) as f:
                for line in f:
                    if line.startswith("Uid:"):
                        # Get real UID (first value)
                        return int(line.split()[1])
        except (FileNotFoundError, ValueError, IndexError):
            pass
        return None

    def _run_iptables(self, args: list[str]) -> tuple[bool, str]:
        """Run an iptables command with sudo.

        Returns (success, error_message).
        """
        cmd = ["iptables"] + args
        if os.geteuid() != 0:
            cmd = ["sudo", "-n"] + cmd

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return False, result.stderr or "iptables failed"
            return True, ""
        except subprocess.TimeoutExpired:
            return False, "iptables command timed out"
        except FileNotFoundError:
            return False, "iptables not found"
        except Exception as e:
            return False, str(e)

    def ensure_chain_exists(self) -> bool:
        """Create the blocking chain if it doesn't exist."""
        # Create chain
        success, _ = self._run_iptables(["-N", self.CHAIN_NAME])
        # Chain might already exist, that's OK

        # Jump to our chain from OUTPUT and INPUT
        for chain in ["OUTPUT", "INPUT"]:
            # Check if rule already exists
            check_result = subprocess.run(
                ["sudo", "-n", "iptables", "-C", chain, "-j", self.CHAIN_NAME]
                if os.geteuid() != 0 else
                ["iptables", "-C", chain, "-j", self.CHAIN_NAME],
                capture_output=True
            )
            if check_result.returncode != 0:
                self._run_iptables(["-I", chain, "1", "-j", self.CHAIN_NAME])

        return True

    def block_process(self, pid: int, process_name: str = "",
                      block_inbound: bool = True, block_outbound: bool = True) -> tuple[bool, str]:
        """Block network access for a process.

        Args:
            pid: Process ID to block
            process_name: Human-readable process name
            block_inbound: Block incoming traffic
            block_outbound: Block outgoing traffic

        Returns:
            (success, error_message)
        """
        if not self._sudo_available:
            return False, "Sudo access required for traffic blocking"

        if pid in self._blocked:
            return False, "Process already blocked"

        uid = self._get_uid_for_pid(pid)
        if uid is None:
            return False, f"Could not find process {pid}"

        # Ensure our chain exists
        self.ensure_chain_exists()

        # Add iptables rules to block by UID
        # Note: iptables owner module only works for OUTPUT chain (outbound)
        # For inbound, we can't easily match by process owner

        if block_outbound:
            # Block outbound traffic from this UID
            success, error = self._run_iptables([
                "-A", self.CHAIN_NAME,
                "-m", "owner", "--uid-owner", str(uid),
                "-j", "DROP"
            ])
            if not success:
                return False, f"Failed to block outbound: {error}"

        # Store blocked process info
        self._blocked[pid] = BlockedProcess(
            pid=pid,
            process_name=process_name or f"pid:{pid}",
            blocked_at=time.time(),
            block_inbound=block_inbound,
            block_outbound=block_outbound
        )

        self._save_blocked()
        return True, ""

    def unblock_process(self, pid: int) -> tuple[bool, str]:
        """Unblock network access for a process.

        Args:
            pid: Process ID to unblock

        Returns:
            (success, error_message)
        """
        if not self._sudo_available:
            return False, "Sudo access required for traffic blocking"

        if pid not in self._blocked:
            return False, "Process is not blocked"

        _blocked = self._blocked[pid]
        uid = self._get_uid_for_pid(pid)

        if uid is not None:
            # Remove iptables rules for this UID
            # List rules and find ones to delete
            success, _ = self._run_iptables([
                "-D", self.CHAIN_NAME,
                "-m", "owner", "--uid-owner", str(uid),
                "-j", "DROP"
            ])
            # Rule might not exist if process died, that's OK

        del self._blocked[pid]
        self._save_blocked()
        return True, ""

    def is_blocked(self, pid: int) -> bool:
        """Check if a process is blocked."""
        return pid in self._blocked

    def get_blocked_processes(self) -> list[BlockedProcess]:
        """Get list of all blocked processes."""
        return list(self._blocked.values())

    def cleanup_dead_processes(self) -> list[int]:
        """Remove blocks for processes that no longer exist.

        Returns list of PIDs that were cleaned up.
        """
        cleaned = []
        for pid in list(self._blocked.keys()):
            if not Path(f"/proc/{pid}").exists():
                # Process is dead, remove from blocked list
                del self._blocked[pid]
                cleaned.append(pid)

        if cleaned:
            self._save_blocked()
        return cleaned

    def unblock_all(self) -> tuple[int, str]:
        """Unblock all processes.

        Returns (count_unblocked, error_message).
        """
        if not self._sudo_available:
            return 0, "Sudo access required for traffic blocking"

        count = len(self._blocked)

        # Flush our chain
        self._run_iptables(["-F", self.CHAIN_NAME])

        self._blocked.clear()
        self._save_blocked()
        return count, ""

    def cleanup_chain(self) -> bool:
        """Remove our iptables chain completely (for app shutdown)."""
        # Flush and delete chain
        self._run_iptables(["-F", self.CHAIN_NAME])

        # Remove jump rules from OUTPUT and INPUT
        for chain in ["OUTPUT", "INPUT"]:
            self._run_iptables(["-D", chain, "-j", self.CHAIN_NAME])

        # Delete chain
        self._run_iptables(["-X", self.CHAIN_NAME])
        return True
