"""Connection tracking via /proc filesystem."""

import os
import socket
import struct
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict

from .services import identify_service
from .protocols import classify_protocol


# Private IP ranges for LAN detection
_PRIVATE_RANGES = [
    (0x0A000000, 0xFF000000),   # 10.0.0.0/8
    (0xAC100000, 0xFFF00000),   # 172.16.0.0/12
    (0xC0A80000, 0xFFFF0000),   # 192.168.0.0/16
    (0x7F000000, 0xFF000000),   # 127.0.0.0/8
    (0xA9FE0000, 0xFFFF0000),   # 169.254.0.0/16
]


@dataclass
class Connection:
    """Represents a single network connection (TCP or UDP)."""
    pid: int | None
    process_name: str
    remote_ip: str
    remote_port: int
    local_port: int
    is_ipv6: bool
    is_private: bool
    service: str | None
    protocol_name: str | None
    protocol: str  # 'tcp' or 'udp'


@dataclass
class ListeningPort:
    """Represents a listening TCP/UDP port."""
    port: int
    protocol: str  # "tcp" or "udp"
    address: str  # e.g., "0.0.0.0", "127.0.0.1", "::"
    process_name: str
    pid: int | None


def _is_private_ip(ip: str) -> bool:
    """Check if IP is in private/LAN range."""
    try:
        n = struct.unpack("!I", socket.inet_aton(ip))[0]
        return any((n & mask) == (base & mask) for base, mask in _PRIVATE_RANGES)
    except OSError:
        # IPv6 — treat link-local / loopback as private
        return ip.startswith("fe80") or ip == "::1" or ip.startswith("::ffff:127.")


def _hex_to_ipv4(h: str) -> str:
    """Convert hex from /proc/net/tcp to IPv4 string."""
    return socket.inet_ntoa(struct.pack("<I", int(h, 16)))


def _hex_to_ipv6(h: str) -> str:
    """Convert hex from /proc/net/tcp6 to IPv6 string."""
    raw = bytes.fromhex(h)
    # Each 4-byte chunk is little-endian
    reordered = b"".join(raw[i:i + 4][::-1] for i in range(0, 16, 4))
    return socket.inet_ntop(socket.AF_INET6, reordered)


def _parse_proc_net(path: str, is_ipv6: bool) -> list[tuple[str, int, int, str]]:
    """Parse /proc/net/tcp or tcp6, return list of (remote_ip, remote_port, local_port, inode)."""
    conns = []
    try:
        with open(path) as f:
            next(f)  # skip header
            for line in f:
                parts = line.split()
                if len(parts) < 10:
                    continue
                if parts[3] != "01":  # 01 = ESTABLISHED
                    continue
                local_addr, local_port_hex = parts[1].split(":")
                remote_addr, remote_port_hex = parts[2].split(":")
                inode = parts[9]
                try:
                    ip = _hex_to_ipv6(remote_addr) if is_ipv6 else _hex_to_ipv4(remote_addr)
                    local_port = int(local_port_hex, 16)
                    remote_port = int(remote_port_hex, 16)
                    conns.append((ip, remote_port, local_port, inode))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return conns


def _parse_proc_net_udp(path: str, is_ipv6: bool) -> list[tuple[str, int, int, str]]:
    """Parse /proc/net/udp or udp6, return list of (remote_ip, remote_port, local_port, inode).

    Note: UDP is connectionless, so we include all entries (no state filtering).
    """
    conns = []
    try:
        with open(path) as f:
            next(f)  # skip header
            for line in f:
                parts = line.split()
                if len(parts) < 10:
                    continue
                # UDP doesn't have ESTABLISHED state, include all entries
                local_addr, local_port_hex = parts[1].split(":")
                remote_addr, remote_port_hex = parts[2].split(":")
                inode = parts[9]
                try:
                    ip = _hex_to_ipv6(remote_addr) if is_ipv6 else _hex_to_ipv4(remote_addr)
                    local_port = int(local_port_hex, 16)
                    remote_port = int(remote_port_hex, 16)
                    # Skip entries with remote address 0.0.0.0:0 (listening only, no remote)
                    if remote_port == 0 and (ip == "0.0.0.0" or ip == "::"):
                        continue
                    conns.append((ip, remote_port, local_port, inode))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return conns


def _build_inode_pid_map() -> dict[str, str]:
    """Map socket inodes to PIDs via /proc/PID/fd."""
    mapping = {}
    for pid_path in Path("/proc").iterdir():
        if not pid_path.name.isdigit():
            continue
        fd_path = pid_path / "fd"
        try:
            for fd in fd_path.iterdir():
                try:
                    link = os.readlink(str(fd))
                    if link.startswith("socket:["):
                        inode = link[8:-1]
                        mapping[inode] = pid_path.name
                except OSError:
                    pass
        except (PermissionError, FileNotFoundError):
            # Process exited or we don't have permission
            pass
    return mapping


def _get_process_name(pid: str) -> str:
    """Get human-readable process name for PID."""
    # Try /proc/PID/status Name field
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("Name:"):
                    return line.split(None, 1)[1].strip()
    except OSError:
        pass
    # Fallback to cmdline basename
    try:
        with open(f"/proc/{pid}/cmdline") as f:
            cmd = f.read().split("\x00")[0]
            if cmd:
                return os.path.basename(cmd)
    except OSError:
        pass
    return f"pid:{pid}"


class ConnectionTracker:
    """Tracks active TCP and UDP connections with process mapping."""

    def get_connections(self) -> list[Connection]:
        """Get all established TCP and UDP connections."""
        # Parse TCP connections
        tcp_conns = _parse_proc_net("/proc/net/tcp", is_ipv6=False)
        tcp_conns.extend(_parse_proc_net("/proc/net/tcp6", is_ipv6=True))

        # Parse UDP connections
        udp_conns = _parse_proc_net_udp("/proc/net/udp", is_ipv6=False)
        udp_conns.extend(_parse_proc_net_udp("/proc/net/udp6", is_ipv6=True))

        # Build inode → PID map
        inode_pid = _build_inode_pid_map()

        # Build connection objects
        result = []

        # Process TCP connections
        for remote_ip, remote_port, local_port, inode in tcp_conns:
            pid_str = inode_pid.get(inode)
            pid = int(pid_str) if pid_str else None
            name = _get_process_name(pid_str) if pid_str else "unknown"

            # Handle IPv4-mapped IPv6 addresses
            display_ip = remote_ip
            is_ipv6 = ":" in remote_ip
            if remote_ip.startswith("::ffff:"):
                display_ip = remote_ip[7:]
                is_ipv6 = False

            is_private = _is_private_ip(display_ip) if not is_ipv6 else True
            service = identify_service(display_ip) if not is_private else None

            # Classify protocol based on remote port
            protocol = classify_protocol(remote_port, is_udp=False)

            result.append(Connection(
                pid=pid,
                process_name=name,
                remote_ip=display_ip,
                remote_port=remote_port,
                local_port=local_port,
                is_ipv6=is_ipv6,
                is_private=is_private,
                service=service,
                protocol_name=protocol,
                protocol="tcp",
            ))

        # Process UDP connections
        for remote_ip, remote_port, local_port, inode in udp_conns:
            pid_str = inode_pid.get(inode)
            pid = int(pid_str) if pid_str else None
            name = _get_process_name(pid_str) if pid_str else "unknown"

            # Handle IPv4-mapped IPv6 addresses
            display_ip = remote_ip
            is_ipv6 = ":" in remote_ip
            if remote_ip.startswith("::ffff:"):
                display_ip = remote_ip[7:]
                is_ipv6 = False

            is_private = _is_private_ip(display_ip) if not is_ipv6 else True
            service = identify_service(display_ip) if not is_private else None

            # Classify protocol based on remote port
            protocol = classify_protocol(remote_port, is_udp=True)

            result.append(Connection(
                pid=pid,
                process_name=name,
                remote_ip=display_ip,
                remote_port=remote_port,
                local_port=local_port,
                is_ipv6=is_ipv6,
                is_private=is_private,
                service=service,
                protocol_name=protocol,
                protocol="udp",
            ))

        return result

    def get_summary(self) -> tuple[dict[str, list[Connection]], dict[str, list[str]]]:
        """
        Get summarized connection data.

        Returns:
            (process_connections, service_ips)
            - process_connections: process_name -> list of connections
            - service_ips: service_name -> list of IP prefixes
        """
        conns = self.get_connections()

        process_connections: dict[str, list[Connection]] = defaultdict(list)
        service_ips: dict[str, list[str]] = defaultdict(list)

        for conn in conns:
            process_connections[conn.process_name].append(conn)

            if conn.service and not conn.is_private:
                # Get first 3 octets
                parts = conn.remote_ip.split(".")
                prefix = ".".join(parts[:3]) + ".x" if len(parts) >= 3 else conn.remote_ip
                if prefix not in service_ips[conn.service]:
                    service_ips[conn.service].append(prefix)
            elif not conn.is_private and conn.service is None:
                parts = conn.remote_ip.split(".")
                prefix = ".".join(parts[:3]) + ".x" if len(parts) >= 3 else conn.remote_ip
                if prefix not in service_ips["(other)"]:
                    service_ips["(other)"].append(prefix)

        return dict(process_connections), dict(service_ips)

    def get_listening_ports(self) -> list[ListeningPort]:
        """Get all listening TCP and UDP ports."""
        results: list[ListeningPort] = []
        seen: set[tuple[int, str, str]] = set()  # (port, protocol, address)

        # Build inode → PID map once
        inode_pid = _build_inode_pid_map()

        # Parse TCP listening sockets (state 0A = LISTEN)
        for path, is_ipv6 in [("/proc/net/tcp", False), ("/proc/net/tcp6", True)]:
            try:
                with open(path) as f:
                    next(f)  # skip header
                    for line in f:
                        parts = line.split()
                        if len(parts) < 10:
                            continue
                        if parts[3] != "0A":  # 0A = LISTEN state
                            continue
                        local_addr, local_port_hex = parts[1].split(":")
                        inode = parts[9]
                        try:
                            port = int(local_port_hex, 16)
                            address = _hex_to_ipv6(local_addr) if is_ipv6 else _hex_to_ipv4(local_addr)
                            # Handle IPv4-mapped IPv6 addresses
                            if address.startswith("::ffff:"):
                                address = address[7:]
                            key = (port, "tcp", address)
                            if key in seen:
                                continue
                            seen.add(key)

                            pid_str = inode_pid.get(inode)
                            pid = int(pid_str) if pid_str else None
                            name = _get_process_name(pid_str) if pid_str else "unknown"

                            results.append(ListeningPort(
                                port=port,
                                protocol="tcp",
                                address=address,
                                process_name=name,
                                pid=pid,
                            ))
                        except Exception:
                            pass
            except FileNotFoundError:
                pass

        # Parse UDP sockets (all entries since UDP is connectionless)
        for path, is_ipv6 in [("/proc/net/udp", False), ("/proc/net/udp6", True)]:
            try:
                with open(path) as f:
                    next(f)  # skip header
                    for line in f:
                        parts = line.split()
                        if len(parts) < 10:
                            continue
                        local_addr, local_port_hex = parts[1].split(":")
                        inode = parts[9]
                        try:
                            port = int(local_port_hex, 16)
                            address = _hex_to_ipv6(local_addr) if is_ipv6 else _hex_to_ipv4(local_addr)
                            # Handle IPv4-mapped IPv6 addresses
                            if address.startswith("::ffff:"):
                                address = address[7:]
                            key = (port, "udp", address)
                            if key in seen:
                                continue
                            seen.add(key)

                            pid_str = inode_pid.get(inode)
                            pid = int(pid_str) if pid_str else None
                            name = _get_process_name(pid_str) if pid_str else "unknown"

                            results.append(ListeningPort(
                                port=port,
                                protocol="udp",
                                address=address,
                                process_name=name,
                                pid=pid,
                            ))
                        except Exception:
                            pass
            except FileNotFoundError:
                pass

        # Sort by port number
        results.sort(key=lambda p: (p.port, p.protocol))
        return results
