#!/usr/bin/env python3
"""NetScope CLI — Terminal-based network monitoring."""

import argparse
import subprocess
import sys
import time
import shutil
import signal
from pathlib import Path

from .core.iptables import IPTablesManager, IPTablesError
from .core.bandwidth import BandwidthCalculator, BandwidthStats
from .core.connections import ConnectionTracker, Connection


def get_primary_interface() -> str:
    """Detect primary network interface."""
    try:
        out = subprocess.check_output(
            ["ip", "route", "get", "8.8.8.8"],
            text=True, stderr=subprocess.DEVNULL
        )
        parts = out.split()
        if "dev" in parts:
            return parts[parts.index("dev") + 1]
    except Exception:
        pass

    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if ":" in line:
                    name = line.split(":")[0].strip()
                    if name != "lo":
                        return name
    except Exception:
        pass

    return "eth0"


def format_bytes(b: float) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def format_rate(bps: float) -> str:
    """Format bytes/sec as human-readable rate."""
    if bps < 1024:
        return f"{bps:6.1f}  B/s"
    elif bps < 1024 ** 2:
        return f"{bps/1024:6.1f} KB/s"
    elif bps < 1024 ** 3:
        return f"{bps/1024**2:6.1f} MB/s"
    else:
        return f"{bps/1024**3:6.1f} GB/s"


def bar(rate: float, max_rate: float, width: int = 20) -> str:
    """Generate ASCII progress bar."""
    if max_rate == 0:
        filled = 0
    else:
        filled = int(width * min(rate / max_rate, 1.0))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


# ──────────────────────────── MONITOR COMMAND ────────────────────────────

def cmd_monitor(args) -> int:
    """Real-time bandwidth monitoring with LAN/Internet split."""
    interface = args.interface or get_primary_interface()
    lan_subnet = args.subnet
    interval = args.interval

    cols = shutil.get_terminal_size((80, 24)).columns

    iptables = IPTablesManager(interface, lan_subnet)

    try:
        print(f"Setting up iptables rules on {interface} (LAN: {lan_subnet})...")
        iptables.setup()
        print("Rules installed. Monitoring... Press Ctrl+C to stop.\n")
    except IPTablesError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Make sure you have sudo access.", file=sys.stderr)
        return 1

    calculator = BandwidthCalculator()
    running = True

    def cleanup(sig=None, frame=None):
        nonlocal running
        if running:
            running = False
            print("\n\nRemoving iptables rules...", end=" ")
            try:
                iptables.teardown()
                print("done.")
            except IPTablesError:
                print("failed.")

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while running:
            counters = iptables.read_counters()
            stats = calculator.update(counters)

            max_rate = max(
                stats.lan_rx_rate, stats.lan_tx_rate,
                stats.inet_rx_rate, stats.inet_tx_rate, 1
            )

            # Clear screen
            print("\033[H\033[J", end="")

            print(f"{'─' * cols}")
            print(f"  Network: {interface}  │  LAN: {lan_subnet}  │  {time.strftime('%H:%M:%S')}")
            print(f"{'─' * cols}")
            print(f"  {'':6}  {'DOWN (RX)':>14}  {'':22}  {'UP (TX)':>14}")
            print(f"{'─' * cols}")

            # LAN row
            print(f"  {'LAN':6}  {format_rate(stats.lan_rx_rate):>14}  "
                  f"{bar(stats.lan_rx_rate, max_rate):22}  {format_rate(stats.lan_tx_rate):>14}")
            print(f"  {'':6}  {'total: ' + format_bytes(stats.lan_rx_total):>14}  "
                  f"{'':22}  {'total: ' + format_bytes(stats.lan_tx_total):>14}")
            print()

            # Internet row
            print(f"  {'INET':6}  {format_rate(stats.inet_rx_rate):>14}  "
                  f"{bar(stats.inet_rx_rate, max_rate):22}  {format_rate(stats.inet_tx_rate):>14}")
            print(f"  {'':6}  {'total: ' + format_bytes(stats.inet_rx_total):>14}  "
                  f"{'':22}  {'total: ' + format_bytes(stats.inet_tx_total):>14}")
            print()

            print(f"{'─' * cols}")

            # Summary
            total_rx = stats.total_rx_rate
            total_tx = stats.total_tx_rate
            inet_rx_pct = stats.inet_rx_percent()
            inet_tx_pct = stats.inet_tx_percent()

            print(f"  Total RX: {format_rate(total_rx):>12}  "
                  f"(LAN {100-inet_rx_pct:.0f}%  /  INET {inet_rx_pct:.0f}%)")
            print(f"  Total TX: {format_rate(total_tx):>12}  "
                  f"(LAN {100-inet_tx_pct:.0f}%  /  INET {inet_tx_pct:.0f}%)")
            print(f"{'─' * cols}")
            print("  Ctrl+C to stop")

            time.sleep(interval)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        cleanup()
        return 1

    return 0


# ──────────────────────────── SNAPSHOT COMMAND ────────────────────────────

def cmd_snapshot(args) -> int:
    """One-shot network snapshot with process connections."""
    tracker = ConnectionTracker()

    # Get connection summary
    proc_conns, service_ips = tracker.get_summary()
    all_conns = tracker.get_connections()

    # Classify connections
    inet_conns = [c for c in all_conns if not c.is_private]
    lan_conns = [c for c in all_conns if c.is_private]
    total_conns = len(all_conns)

    sep = "─" * 52

    print()
    print("Network Snapshot")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Traffic classification
    print("Traffic Classification")
    if total_conns == 0:
        print("  No active TCP connections detected.")
    elif len(lan_conns) == 0:
        print(f"  All {total_conns} active connection(s) are going to the internet")
        print("  — zero LAN traffic right now.")
    elif len(inet_conns) == 0:
        print(f"  All {total_conns} active connection(s) are on the LAN")
        print("  — zero internet traffic right now.")
    else:
        pct_inet = 100 * len(inet_conns) / total_conns
        print(f"  {total_conns} active connections:  "
              f"{len(inet_conns)} internet ({pct_inet:.0f}%),  "
              f"{len(lan_conns)} LAN ({100-pct_inet:.0f}%)")

    # Per-process table
    print()
    print(f"  {'Process':<28} {'Internet':>10}  {'LAN':>6}")
    print(f"  {sep}")

    sorted_procs = sorted(
        proc_conns.items(),
        key=lambda kv: sum(1 for c in kv[1] if not c.is_private),
        reverse=True,
    )

    for name, conns in sorted_procs:
        i = sum(1 for c in conns if not c.is_private)
        l = sum(1 for c in conns if c.is_private)
        if i + l == 0:
            continue
        i_str = str(i) if i else "-"
        l_str = str(l) if l else "-"
        print(f"  {name:<28} {i_str:>10}  {l_str:>6}")

    # Remote services
    if service_ips:
        print()
        print("Remote Destinations")
        for svc, ips in sorted(service_ips.items(), key=lambda kv: kv[0] == "(other)"):
            addr_str = ", ".join(ips[:3])
            if len(ips) > 3:
                addr_str += f" +{len(ips) - 3}"
            print(f"  {svc:<22} {addr_str}")

    print()

    if args.watch:
        try:
            while True:
                print(f"\nRefreshing in {args.watch} seconds... (Ctrl+C to stop)")
                time.sleep(args.watch)
                print("\033[H\033[J", end="")  # Clear screen for next iteration

                # Re-fetch data
                tracker = ConnectionTracker()
                proc_conns, service_ips = tracker.get_summary()
                all_conns = tracker.get_connections()
                inet_conns = [c for c in all_conns if not c.is_private]
                lan_conns = [c for c in all_conns if c.is_private]
                total_conns = len(all_conns)

                # Print snapshot again
                print()
                print("Network Snapshot")
                print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print()

                print("Traffic Classification")
                if total_conns == 0:
                    print("  No active TCP connections detected.")
                elif len(lan_conns) == 0:
                    print(f"  All {total_conns} active connection(s) are going to the internet")
                    print("  — zero LAN traffic right now.")
                elif len(inet_conns) == 0:
                    print(f"  All {total_conns} active connection(s) are on the LAN")
                    print("  — zero internet traffic right now.")
                else:
                    pct_inet = 100 * len(inet_conns) / total_conns
                    print(f"  {total_conns} active connections:  "
                          f"{len(inet_conns)} internet ({pct_inet:.0f}%),  "
                          f"{len(lan_conns)} LAN ({100-pct_inet:.0f}%)")

                print()
                print(f"  {'Process':<28} {'Internet':>10}  {'LAN':>6}")
                print(f"  {sep}")

                sorted_procs = sorted(
                    proc_conns.items(),
                    key=lambda kv: sum(1 for c in kv[1] if not c.is_private),
                    reverse=True,
                )

                for name, conns in sorted_procs:
                    i = sum(1 for c in conns if not c.is_private)
                    l = sum(1 for c in conns if c.is_private)
                    if i + l == 0:
                        continue
                    i_str = str(i) if i else "-"
                    l_str = str(l) if l else "-"
                    print(f"  {name:<28} {i_str:>10}  {l_str:>6}")

                if service_ips:
                    print()
                    print("Remote Destinations")
                    for svc, ips in sorted(service_ips.items(), key=lambda kv: kv[0] == "(other)"):
                        addr_str = ", ".join(ips[:3])
                        if len(ips) > 3:
                            addr_str += f" +{len(ips) - 3}"
                        print(f"  {svc:<22} {addr_str}")

                print()

        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

    return 0


# ──────────────────────────── STATUS COMMAND ────────────────────────────

def cmd_status(args) -> int:
    """Quick one-line status."""
    interface = args.interface or get_primary_interface()

    # Read interface stats
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if interface + ":" in line:
                    cols = line.split(":")[1].split()
                    rx_total = int(cols[0])
                    tx_total = int(cols[8])
                    break
            else:
                print(f"Interface {interface} not found", file=sys.stderr)
                return 1
    except FileNotFoundError:
        print("Could not read /proc/net/dev", file=sys.stderr)
        return 1

    # Sample rate
    time.sleep(1)

    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if interface + ":" in line:
                    cols = line.split(":")[1].split()
                    rx2 = int(cols[0])
                    tx2 = int(cols[8])
                    break
    except FileNotFoundError:
        pass

    rx_rate = rx2 - rx_total
    tx_rate = tx2 - tx_total

    # Count connections
    tracker = ConnectionTracker()
    conns = tracker.get_connections()
    inet_count = sum(1 for c in conns if not c.is_private)

    print(f"{interface}: ↓{format_rate(rx_rate)} ↑{format_rate(tx_rate)} | "
          f"{len(conns)} conns ({inet_count} internet) | "
          f"total: ↓{format_bytes(rx2)} ↑{format_bytes(tx2)}")

    return 0


# ──────────────────────────── PORTS COMMAND ────────────────────────────

def cmd_ports(args) -> int:
    """Show listening TCP/UDP ports."""
    from .core.connections import ConnectionTracker

    tracker = ConnectionTracker()
    ports = tracker.get_listening_ports()

    # Filter by protocol if requested
    if args.tcp:
        ports = [p for p in ports if p.protocol == "tcp"]
    elif args.udp:
        ports = [p for p in ports if p.protocol == "udp"]

    print("Listening Ports:")
    print()
    print(f"  {'Port':<8} {'Proto':<6} {'Address':<20} {'Process':<20} {'PID':>8}")
    print("  " + "─" * 66)

    for p in sorted(ports, key=lambda x: (x.port, x.protocol)):
        addr = p.address if p.address else "*"
        if addr == "0.0.0.0":
            addr = "* (all)"
        elif addr == "::":
            addr = "* (all IPv6)"
        name = p.process_name[:18] + ".." if len(p.process_name) > 20 else p.process_name
        pid_str = str(p.pid) if p.pid else "-"
        print(f"  {p.port:<8} {p.protocol:<6} {addr:<20} {name:<20} {pid_str:>8}")

    print()
    print(f"  Total: {len(ports)} listening port(s)")

    return 0


# ──────────────────────────── PROCESSES COMMAND ────────────────────────────

def cmd_processes(args) -> int:
    """Show per-process network usage."""
    from .core.connections import ConnectionTracker
    from .core.process_bandwidth import ProcessBandwidthTracker

    tracker = ConnectionTracker()
    bw_tracker = ProcessBandwidthTracker()

    def show_stats():
        conns = tracker.get_connections()
        stats = bw_tracker.get_process_stats(
            total_rx_rate=0,  # No actual bandwidth measurement in CLI
            total_tx_rate=0
        )

        print()
        print(f"Per-Process Network Usage  ({time.strftime('%H:%M:%S')})")
        print()
        print(f"  {'Process':<24} {'Conns':>6} {'TCP':>5} {'UDP':>5} {'Internet':>9} {'LAN':>5}")
        print("  " + "─" * 62)

        # Sort by total connections
        sorted_stats = sorted(stats, key=lambda s: s.connection_count, reverse=True)

        for s in sorted_stats[:20]:
            name = s.process_name[:22] + ".." if len(s.process_name) > 24 else s.process_name
            tcp = sum(1 for c in conns if c.process_name == s.process_name and c.protocol == "tcp")
            udp = sum(1 for c in conns if c.process_name == s.process_name and c.protocol == "udp")
            print(f"  {name:<24} {s.connection_count:>6} {tcp:>5} {udp:>5} {s.inet_connections:>9} {s.lan_connections:>5}")

        print()
        print(f"  Total processes: {len(stats)}")

    if args.watch:
        try:
            while True:
                print("\033[H\033[J", end="")  # Clear screen
                show_stats()
                print(f"\n  Refreshing in {args.watch} seconds... (Ctrl+C to stop)")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0
    else:
        show_stats()

    return 0


# ──────────────────────────── INTERFACES COMMAND ────────────────────────────

def cmd_interfaces(args) -> int:
    """List available network interfaces."""
    print("Network Interfaces:")
    print()

    try:
        with open("/proc/net/dev") as f:
            next(f)  # skip headers
            for line in f:
                if ":" in line:
                    name = line.split(":")[0].strip()
                    cols = line.split(":")[1].split()
                    rx = int(cols[0])
                    tx = int(cols[8])

                    # Check if up
                    try:
                        with open(f"/sys/class/net/{name}/operstate") as sf:
                            state = sf.read().strip()
                    except FileNotFoundError:
                        state = "unknown"

                    status = "up" if state == "up" else state
                    print(f"  {name:<16} {status:>8}  ↓{format_bytes(rx):>12}  ↑{format_bytes(tx):>12}")
    except FileNotFoundError:
        print("  Could not read /proc/net/dev", file=sys.stderr)
        return 1

    return 0


# ──────────────────────────── MAIN ────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="netscope",
        description="Linux network monitoring tool"
    )
    parser.set_defaults(func=lambda args: parser.print_help())

    subparsers = parser.add_subparsers(
        title="commands",
        metavar="COMMAND"
    )

    # monitor command
    p_monitor = subparsers.add_parser(
        "monitor", aliases=["mon"],
        help="Real-time bandwidth monitoring with LAN/Internet split"
    )
    p_monitor.add_argument(
        "-i", "--interface",
        help="Network interface to monitor (auto-detected by default)"
    )
    p_monitor.add_argument(
        "-s", "--subnet",
        default="192.168.0.0/20",
        help="LAN subnet for classification (default: 192.168.0.0/20)"
    )
    p_monitor.add_argument(
        "-n", "--interval",
        type=float,
        default=1.0,
        help="Update interval in seconds (default: 1.0)"
    )
    p_monitor.set_defaults(func=cmd_monitor)

    # snapshot command
    p_snapshot = subparsers.add_parser(
        "snapshot", aliases=["snap"],
        help="One-shot network snapshot with process connections"
    )
    p_snapshot.add_argument(
        "-w", "--watch",
        type=float,
        metavar="SECS",
        help="Continuously refresh every SECS seconds"
    )
    p_snapshot.set_defaults(func=cmd_snapshot)

    # status command
    p_status = subparsers.add_parser(
        "status",
        help="Quick one-line status"
    )
    p_status.add_argument(
        "-i", "--interface",
        help="Network interface (auto-detected by default)"
    )
    p_status.set_defaults(func=cmd_status)

    # interfaces command
    p_ifaces = subparsers.add_parser(
        "interfaces", aliases=["if"],
        help="List available network interfaces"
    )
    p_ifaces.set_defaults(func=cmd_interfaces)

    # ports command (listening ports)
    p_ports = subparsers.add_parser(
        "ports", aliases=["listening"],
        help="Show listening TCP/UDP ports"
    )
    p_ports.add_argument(
        "-t", "--tcp",
        action="store_true",
        help="Show only TCP ports"
    )
    p_ports.add_argument(
        "-u", "--udp",
        action="store_true",
        help="Show only UDP ports"
    )
    p_ports.set_defaults(func=cmd_ports)

    # processes command (per-process bandwidth)
    p_procs = subparsers.add_parser(
        "processes", aliases=["procs"],
        help="Show per-process network usage"
    )
    p_procs.add_argument(
        "-w", "--watch",
        type=float,
        metavar="SECS",
        help="Continuously refresh every SECS seconds"
    )
    p_procs.set_defaults(func=cmd_processes)

    args = parser.parse_args()
    return args.func(args)  # type: ignore[no-any-return]


if __name__ == "__main__":
    sys.exit(main())
