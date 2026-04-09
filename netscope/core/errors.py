"""Centralized error handling and logging for NetScope."""

import logging
import functools
from typing import Callable, TypeVar, ParamSpec
from enum import Enum

P = ParamSpec("P")
T = TypeVar("T")


class ErrorCategory(Enum):
    """Categories of errors for grouping."""
    IPTABLES = "iptables"
    PROC_FS = "proc_fs"
    NETWORK = "network"
    PERMISSION = "permission"
    CONFIG = "config"
    GUI = "gui"


class NetScopeError(Exception):
    """Base exception for NetScope errors."""
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.GUI):
        super().__init__(message)
        self.category = category


class IPTablesError(NetScopeError):
    """Error in iptables operations."""
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.IPTABLES)


class ProcFsError(NetScopeError):
    """Error reading /proc filesystem."""
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.PROC_FS)


class NetworkError(NetScopeError):
    """Error in network operations."""
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.NETWORK)


class PermissionError(NetScopeError):
    """Error due to insufficient permissions."""
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.PERMISSION)


class ConfigError(NetScopeError):
    """Error in configuration."""
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.CONFIG)


# Configure logging
logger = logging.getLogger("netscope")


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )


def safe_call(
    default=None,
    log_errors: bool = True,
    error_message: str = ""
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to safely call a function and return default on error.

    Args:
        default: Value to return on error
        log_errors: Whether to log errors
        error_message: Custom error message prefix

    Returns:
        Decorated function that catches exceptions
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    msg = error_message or f"Error in {func.__name__}"
                    logger.debug(f"{msg}: {e}")
                return default  # type: ignore[no-any-return]
        return wrapper
    return decorator


def log_errors(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to log errors without suppressing them."""
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper
