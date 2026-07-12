"""Integration tests for the circuit breaker service."""
from __future__ import annotations

import pytest

from app.services.circuit_breaker import (
    CircuitBreaker,
    CBState,
    get_circuit_breaker,
    all_circuit_breaker_statuses,
)


class TestCircuitBreaker:
    def _make_cb(self, threshold=3, cooldown=60.0) -> CircuitBreaker:
        return CircuitBreaker("test_cb", failure_threshold=threshold, cooldown_seconds=cooldown)

    def test_initial_state_is_closed(self):
        cb = self._make_cb()
        assert cb.state == CBState.CLOSED

    def test_allows_request_when_closed(self):
        cb = self._make_cb()
        assert cb.allow_request() is True

    def test_trips_after_threshold_failures(self):
        cb = self._make_cb(threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CBState.CLOSED  # still closed
        cb.record_failure()
        assert cb.state == CBState.OPEN    # tripped

    def test_blocks_request_when_open(self):
        cb = self._make_cb(threshold=1)
        cb.record_failure()
        assert cb.state == CBState.OPEN
        assert cb.allow_request() is False

    def test_success_resets_to_closed(self):
        cb = self._make_cb(threshold=1)
        cb.record_failure()
        assert cb.state == CBState.OPEN
        cb.record_success()
        assert cb.state == CBState.CLOSED
        assert cb.allow_request() is True

    def test_half_open_after_cooldown(self):
        import time
        cb = CircuitBreaker("t", failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure()
        assert cb.state == CBState.OPEN
        time.sleep(0.02)
        # After cooldown, state should transition to HALF_OPEN on next check.
        assert cb.state == CBState.HALF_OPEN

    def test_probe_success_closes_circuit(self):
        import time
        cb = CircuitBreaker("t", failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.allow_request() is True   # probe allowed
        cb.record_success()
        assert cb.state == CBState.CLOSED

    def test_probe_failure_reopens_circuit(self):
        import time
        cb = CircuitBreaker("t", failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.allow_request() is True   # probe allowed
        cb.record_failure()   # probe fails
        assert cb.state == CBState.OPEN

    def test_status_dict_structure(self):
        cb = self._make_cb()
        status = cb.status_dict()
        assert "circuit" in status
        assert "state" in status
        assert "failures" in status
        assert "threshold" in status

    def test_singleton_registry(self):
        cb1 = get_circuit_breaker("singleton_test")
        cb2 = get_circuit_breaker("singleton_test")
        assert cb1 is cb2

    def test_all_statuses_returns_list(self):
        statuses = all_circuit_breaker_statuses()
        assert isinstance(statuses, list)
