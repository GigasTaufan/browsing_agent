"""Unit test aktivasi MLflow GenAI tracing."""

import sys
from unittest.mock import Mock

import pytest

import main


@pytest.fixture()
def mlflow_mock(monkeypatch):
    """Suntik modul mlflow palsu agar tidak ada panggilan jaringan."""
    mock = Mock()
    monkeypatch.setitem(sys.modules, "mlflow", mock)
    return mock


def test_setup_tracing_disabled_is_noop(monkeypatch, mlflow_mock):
    monkeypatch.setattr(main.config, "MLFLOW_TRACING_ENABLED", False)

    result = main.setup_tracing(verbose=True)

    assert result is None
    mlflow_mock.set_tracking_uri.assert_not_called()
    mlflow_mock.langchain.autolog.assert_not_called()


def test_setup_tracing_enabled_configures_mlflow(monkeypatch, mlflow_mock):
    monkeypatch.setattr(main.config, "MLFLOW_TRACING_ENABLED", True)
    monkeypatch.setattr(main.config, "MLFLOW_TRACKING_URI", "http://mlflow.example:5000")
    monkeypatch.setattr(main.config, "MLFLOW_EXPERIMENT_NAME", "exp-test")

    result = main.setup_tracing(verbose=True)

    assert result is mlflow_mock
    mlflow_mock.set_tracking_uri.assert_called_once_with("http://mlflow.example:5000")
    mlflow_mock.set_experiment.assert_called_once_with("exp-test")
    mlflow_mock.langchain.autolog.assert_called_once_with()


def test_setup_tracing_is_non_fatal_on_error(monkeypatch, mlflow_mock):
    monkeypatch.setattr(main.config, "MLFLOW_TRACING_ENABLED", True)
    mlflow_mock.set_experiment.side_effect = ConnectionError("server unreachable")

    result = main.setup_tracing()

    assert result is None
    mlflow_mock.langchain.autolog.assert_not_called()
