import math
from dataclasses import dataclass
from numbers import Integral, Real

from .errors import BridgeInputError


def integer(value):
    return isinstance(value, Integral) and not isinstance(value, bool)


def invalid(reason):
    raise BridgeInputError("invalid_config", reason)


@dataclass(frozen=True)
class SamplingConfig:
    time_limit_seconds: float = 60
    memory_limit_bytes: int = 2**31
    max_draws_per_chain: int = 10_000
    stopping: str = "diagnostics"

    def __post_init__(self):
        t = self.time_limit_seconds
        if isinstance(t, bool) or not isinstance(t, Real) or not math.isfinite(t) or t <= 0:
            invalid("time_limit_seconds must be finite and positive")
        if not integer(self.memory_limit_bytes) or self.memory_limit_bytes <= 0:
            invalid("memory_limit_bytes must be a positive integer")
        if not integer(self.max_draws_per_chain) or self.max_draws_per_chain < 500:
            invalid("max_draws_per_chain must be at least 500")
        if self.stopping not in ("diagnostics", "fixed_iterations"):
            invalid("stopping must be diagnostics or fixed_iterations")
        object.__setattr__(self, "time_limit_seconds", float(self.time_limit_seconds))
        object.__setattr__(self, "memory_limit_bytes", int(self.memory_limit_bytes))
        object.__setattr__(self, "max_draws_per_chain", int(self.max_draws_per_chain))
        object.__setattr__(self, "stopping", str(self.stopping))


def windows(value):
    pair = (value, value) if integer(value) else value
    if not isinstance(pair, tuple) or len(pair) != 2:
        invalid("window_size must be an integer or pair of integers")
    if any(not integer(v) or v < 20 for v in pair):
        invalid("each window requires at least 20 increments")
    return tuple(int(v) for v in pair)


def validate_request(window_size, random_state, n_samples, sampling):
    pair = windows(window_size)
    if random_state is not None and (not integer(random_state) or not 0 <= random_state < 2**64):
        invalid("random_state must be an integer in [0, 2**64) or None")
    if not isinstance(sampling, SamplingConfig):
        invalid("sampling must be SamplingConfig")
    if (
        not integer(n_samples)
        or n_samples < 2000
        or n_samples % 4
        or n_samples > 4 * sampling.max_draws_per_chain
    ):
        invalid("n_samples must be >=2000, divisible by four, and within the draw cap")
    return pair
