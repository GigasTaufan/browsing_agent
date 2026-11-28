"""Unit test aktivasi MLflow GenAI tracing."""

import sys
from unittest.mock import Mock

import pytest

import main


@pytest.fixture()
def mlflow_mock(monkeypatch):
    mock = Mock()
    monkeypatch.setitem(sys.modules, "mlflow", mock)
    monkeypatch.setattr(main, "_mlflow", None)
    return mock


def test_setup_tracing_disabled_is_noop(monkeypatch, mlflow_mock):
    monkeypatch.setattr(main.config, "MLFLOW_TRACING_ENABLED", False)

    result = main.setup_tracing(verbose=True)

    assert result is None
    mlflow_mock.set_tracking_uri.assert_not_called()
    mlflow_mock.langchain.autolog.assert_not_called()


def test_setup_tracing_uses_existing_experiment_id(monkeypatch, mlflow_mock):
    monkeypatch.setattr(main.config, "MLFLOW_TRACING_ENABLED", True)
    monkeypatch.setattr(main.config, "MLFLOW_TRACKING_URI", "http://localhost:5000")
    monkeypatch.setattr(main.config, "MLFLOW_EXPERIMENT_ID", "1")
    monkeypatch.setattr(main, "_mlflow_reachable", lambda uri, timeout=2.0: True)

    result = main.setup_tracing(verbose=True)

    assert result is mlflow_mock
    mlflow_mock.set_tracking_uri.assert_called_once_with("http://localhost:5000")
    mlflow_mock.set_experiment.assert_called_once_with(experiment_id="1")
    mlflow_mock.langchain.autolog.assert_called_once_with()


def test_setup_tracing_skips_fast_when_server_unreachable(monkeypatch, mlflow_mock):
    """Server black-hole: skip tracing tanpa memanggil mlflow sama sekali."""
    monkeypatch.setattr(main.config, "MLFLOW_TRACING_ENABLED", True)
    monkeypatch.setattr(main.config, "MLFLOW_TRACKING_URI", "http://10.255.255.1:5000")
    monkeypatch.setattr(main, "_mlflow_reachable", lambda uri, timeout=2.0: False)

    result = main.setup_tracing(verbose=True)

    assert result is None
    mlflow_mock.set_tracking_uri.assert_not_called()
    mlflow_mock.set_experiment.assert_not_called()
    mlflow_mock.langchain.autolog.assert_not_called()


def test_setup_tracing_is_non_fatal_on_error(monkeypatch, mlflow_mock):
    monkeypatch.setattr(main.config, "MLFLOW_TRACING_ENABLED", True)
    monkeypatch.setattr(main, "_mlflow_reachable", lambda uri, timeout=2.0: True)
    mlflow_mock.set_experiment.side_effect = ConnectionError("server unreachable")

    result = main.setup_tracing()

    assert result is None
    mlflow_mock.langchain.autolog.assert_not_called()
