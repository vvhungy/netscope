"""IPTables chain management for bandwidth counting."""

import logging
import subprocess

from ..config import IPTABLES_CHAIN, RULE_TAGS
from .errors import IPTablesError

logger = logging.getLogger("netscope.iptables")


class IPTablesManager:
    """Manages iptables chain and counting rules for bandwidth monitoring."""

    def __init__(self, interface: str, lan_subnet: str):
        self.interface = interface
        self.lan_subnet = lan_subnet
        self.chain = IPTABLES_CHAIN
        self._setup_done = False

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run an iptables command via sudo."""
        cmd = ["sudo", "iptables", *args]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            raise IPTablesError(f"iptables failed: {result.stderr.strip()}")
        return result

    def setup(self) -> None:
        """Create chain and install counting rules."""
        # Create chain (ignore if exists)
        self._run("-N", self.chain, check=False)

        # Flush existing rules in our chain
        self._run("-F", self.chain)

        # LAN TX: outgoing to LAN subnet
        self._run("-A", self.chain, "-o", self.interface,
                  "-d", self.lan_subnet, "-m", "comment",
                  "--comment", RULE_TAGS["lan_tx"])

        # LAN RX: incoming from LAN subnet
        self._run("-A", self.chain, "-i", self.interface,
                  "-s", self.lan_subnet, "-m", "comment",
                  "--comment", RULE_TAGS["lan_rx"])

        # Internet TX: outgoing NOT to LAN
        self._run("-A", self.chain, "-o", self.interface,
                  "!", "-d", self.lan_subnet, "-m", "comment",
                  "--comment", RULE_TAGS["inet_tx"])

        # Internet RX: incoming NOT from LAN
        self._run("-A", self.chain, "-i", self.interface,
                  "!", "-s", self.lan_subnet, "-m", "comment",
                  "--comment", RULE_TAGS["inet_rx"])

        # Hook into OUTPUT chain
        res = self._run("-C", "OUTPUT", "-j", self.chain, check=False)
        if res.returncode != 0:
            self._run("-I", "OUTPUT", "1", "-j", self.chain)

        # Hook into INPUT chain
        res = self._run("-C", "INPUT", "-j", self.chain, check=False)
        if res.returncode != 0:
            self._run("-I", "INPUT", "1", "-j", self.chain)

        self._setup_done = True

    def teardown(self) -> None:
        """Remove chain and rules."""
        # Unhook from OUTPUT and INPUT
        self._run("-D", "OUTPUT", "-j", self.chain, check=False)
        self._run("-D", "INPUT", "-j", self.chain, check=False)

        # Flush and delete chain
        self._run("-F", self.chain, check=False)
        self._run("-X", self.chain, check=False)

        self._setup_done = False

    def read_counters(self) -> dict[str, int]:
        """Read byte counters from chain rules."""
        result = self._run("-L", self.chain, "-v", "-n", "-x")
        counters: dict[str, int] = {}

        for line in result.stdout.splitlines():
            for key, tag in RULE_TAGS.items():
                if tag in line:
                    parts = line.split()
                    try:
                        counters[key] = int(parts[1])  # bytes column
                    except (IndexError, ValueError):
                        counters[key] = 0

        # Ensure all counters present
        for key in RULE_TAGS:
            counters.setdefault(key, 0)

        return counters

    @staticmethod
    def check_sudo() -> bool:
        """Check if we can run sudo iptables."""
        try:
            result = subprocess.run(
                ["sudo", "iptables", "-L"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
