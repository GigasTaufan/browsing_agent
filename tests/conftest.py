"""Konfigurasi pytest untuk seluruh suite."""

import os

# Nonaktifkan async trace logging MLflow di lingkungan test agar tidak ada
# background queue yang mem-flush ke tracking server saat proses exit.
os.environ.setdefault("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
