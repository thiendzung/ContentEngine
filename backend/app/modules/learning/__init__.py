"""Learning loop module boundary."""

from app.modules.learning.performance_signal import (
    PerformanceSignalError,
    PerformanceSignalResult,
    materialize_performance_signal,
)

__all__ = [
    "PerformanceSignalError",
    "PerformanceSignalResult",
    "materialize_performance_signal",
]
