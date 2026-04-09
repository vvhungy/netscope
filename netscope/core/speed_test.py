"""Network speed test functionality.

Provides bandwidth testing using either:
1. speedtest-cli (if installed)
2. Built-in HTTP download/upload tests

The speed test measures actual network throughput to various servers.
"""

import os
import subprocess
import time
import urllib.request
import urllib.error
import json
import socket
from dataclasses import dataclass
from typing import Optional, Callable
from threading import Event


@dataclass
class SpeedTestResult:
    """Result of a speed test."""
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    ping_ms: float = 0.0
    server: str = ""
    timestamp: str = ""
    error: str = ""


class SpeedTest:
    """Network speed test using multiple methods."""

    DOWNLOAD_URLS = [
        "https://speed.cloudflare.com/__down?bytes=10000000",
        "https://proof.ovh.net/files/10Mb.dat",
    ]

    UPLOAD_URL = "https://httpbin.org/post"

    def __init__(self):
        self._stop_event = Event()
        self._speedtest_cli = self._find_speedtest_cli()

    def _find_speedtest_cli(self) -> Optional[str]:
        """Find speedtest-cli executable."""
        for cmd in ["speedtest-cli", "speedtest"]:
            result = subprocess.run(["which", cmd], capture_output=True, text=True)
            if result.returncode == 0:
                return cmd
        return None

    def has_speedtest_cli(self) -> bool:
        """Check if speedtest-cli is available."""
        return self._speedtest_cli is not None

    def stop(self) -> None:
        """Stop any running test."""
        self._stop_event.set()

    def run_speedtest_cli(self, progress_callback: Optional[Callable[[str], None]] = None) -> SpeedTestResult:
        """Run speed test using speedtest-cli."""
        if not self._speedtest_cli:
            return SpeedTestResult(error="speedtest-cli not found")

        if progress_callback:
            progress_callback("Starting speedtest-cli...")

        try:
            result = subprocess.run(
                [self._speedtest_cli, "--json"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                return SpeedTestResult(error=f"speedtest-cli failed: {result.stderr}")

            data = json.loads(result.stdout)

            # Handle both old and new speedtest-cli JSON formats
            # Old format: {"download": bandwidth_in_bits, "upload": bandwidth_in_bits}
            # New format: {"download": {"bandwidth": ...}, "upload": {"bandwidth": ...}}
            download_data = data.get("download", 0)
            upload_data = data.get("upload", 0)

            if isinstance(download_data, dict):
                download_mbps = download_data.get("bandwidth", 0) / 1_000_000
            else:
                download_mbps = float(download_data) / 1_000_000

            if isinstance(upload_data, dict):
                upload_mbps = upload_data.get("bandwidth", 0) / 1_000_000
            else:
                upload_mbps = float(upload_data) / 1_000_000

            ping_data = data.get("ping", 0)
            if isinstance(ping_data, dict):
                ping_ms = ping_data.get("latency", 0)
            else:
                ping_ms = float(ping_data)

            return SpeedTestResult(
                download_mbps=download_mbps,
                upload_mbps=upload_mbps,
                ping_ms=ping_ms,
                server=data.get("server", {}).get("name", "Unknown"),
                timestamp=data.get("timestamp", "")
            )

        except subprocess.TimeoutExpired:
            return SpeedTestResult(error="Speed test timed out")
        except json.JSONDecodeError as e:
            return SpeedTestResult(error=f"Failed to parse results: {e}")
        except Exception as e:
            return SpeedTestResult(error=str(e))

    def run_builtin_test(
        self,
        test_download: bool = True,
        test_upload: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> SpeedTestResult:
        """Run built-in speed test using HTTP."""
        self._stop_event.clear()
        result = SpeedTestResult(server="Built-in HTTP test")

        try:
            if progress_callback:
                progress_callback("Testing ping...")
            result.ping_ms = self._test_ping()

            if self._stop_event.is_set():
                result.error = "Cancelled"
                return result

            if test_download:
                if progress_callback:
                    progress_callback("Testing download speed...")
                result.download_mbps = self._test_download(progress_callback)

            if self._stop_event.is_set():
                result.error = "Cancelled"
                return result

            if test_upload:
                if progress_callback:
                    progress_callback("Testing upload speed...")
                result.upload_mbps = self._test_upload(progress_callback)

        except Exception as e:
            result.error = str(e)

        return result

    def _test_ping(self, host: str = "8.8.8.8", count: int = 3) -> float:
        """Test ping latency."""
        try:
            latencies = []
            for _ in range(count):
                start = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                try:
                    sock.connect((host, 53))
                    latencies.append((time.time() - start) * 1000)
                except (socket.timeout, socket.error):
                    pass
                finally:
                    sock.close()

            if latencies:
                return sum(latencies) / len(latencies)
            return 0.0
        except Exception:
            return 0.0

    def _test_download(self, progress_callback: Optional[Callable[[str], None]] = None) -> float:
        """Test download speed using HTTP."""
        best_speed = 0.0

        for url in self.DOWNLOAD_URLS:
            if self._stop_event.is_set():
                break

            try:
                start = time.time()
                req = urllib.request.Request(url, headers={"User-Agent": "NetScope-SpeedTest/1.0"})

                with urllib.request.urlopen(req, timeout=15) as response:
                    bytes_downloaded = 0
                    chunk_size = 8192

                    while True:
                        if self._stop_event.is_set():
                            return best_speed

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        bytes_downloaded += len(chunk)

                    elapsed = time.time() - start
                    if elapsed > 0:
                        speed_mbps = (bytes_downloaded * 8) / (elapsed * 1_000_000)
                        best_speed = max(best_speed, speed_mbps)

                if best_speed > 10:
                    break

            except (urllib.error.URLError, socket.timeout):
                continue
            except Exception:
                continue

        return best_speed

    def _test_upload(self, progress_callback: Optional[Callable[[str], None]] = None) -> float:
        """Test upload speed using HTTP POST."""
        if self._stop_event.is_set():
            return 0.0

        try:
            test_data = os.urandom(1_000_000)
            start = time.time()

            req = urllib.request.Request(
                self.UPLOAD_URL,
                data=test_data,
                headers={
                    "User-Agent": "NetScope-SpeedTest/1.0",
                    "Content-Type": "application/octet-stream"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                response.read()

            elapsed = time.time() - start
            if elapsed > 0:
                return (len(test_data) * 8) / (elapsed * 1_000_000)

        except Exception:
            pass

        return 0.0

    def run(
        self,
        use_cli: bool = True,
        test_download: bool = True,
        test_upload: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> SpeedTestResult:
        """Run speed test using best available method.

        If use_cli is True and speedtest-cli is available, it will be tried first.
        If CLI fails (e.g., 403 error, timeout), automatically falls back to builtin HTTP test.
        """
        if use_cli and self._speedtest_cli:
            result = self.run_speedtest_cli(progress_callback)
            # If CLI failed, fallback to builtin test
            if result.error:
                if progress_callback:
                    progress_callback(f"CLI failed ({result.error[:50]}), using HTTP test...")
                return self.run_builtin_test(test_download, test_upload, progress_callback)
            return result
        else:
            return self.run_builtin_test(test_download, test_upload, progress_callback)
