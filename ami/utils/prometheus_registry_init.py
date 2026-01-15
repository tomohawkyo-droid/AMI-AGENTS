#!/usr/bin/env bash
""":'
exec "$(dirname "$0")/../ami-run" "$0" "$@"
"""

"""Utility script to initialize Prometheus configuration in base storage registry."""

# Standard library imports FIRST
from pathlib import Path  # noqa: E402
import sys  # noqa: E402


# Bootstrap sys.path - MUST come before base imports (following pattern from base scripts)
sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "base").exists())))

# Now we can import from base
from base.backend.dataops.storage.registry import StorageRegistry  # noqa: E402
from base.scripts.env.paths import setup_imports  # noqa: E402
from agents.ami.cli_components.confirmation_dialog import confirm  # noqa: E402


# Setup imports and get roots
ORCHESTRATOR_ROOT, _ = setup_imports()


def initialize_prometheus_config_in_registry():
    """Initialize default Prometheus configuration in the base storage registry."""
    try:
        # Connect to storage registry
        registry = StorageRegistry()

        # Create default Prometheus configuration
        default_config = """# Prometheus configuration for AMI Orchestrator
# Managed by base storage registry

global:
  scrape_interval:     15s
  evaluation_interval: 15s
  # scrape_timeout is set to the global default (10s)

# Alertmanager configuration
alerting:
  alertmanagers:
  - static_configs:
    - targets:
      # - alertmanager:9093

# Load rules once and periodically evaluate them according to the global 'evaluation_interval'.
rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

# A scrape configuration containing exactly one endpoint to scrape:
# Here it's Prometheus itself.
scrape_configs:
  # The job name is added as a label 'job=<job_name>' to any timeseries scraped from this config.
  - job_name: 'prometheus'
    # Override the global default and scrape targets from this job every 5 seconds.
    scrape_interval: 5s
    static_configs:
    - targets: ['localhost:9090']

  # AMI Orchestrator services
  - job_name: 'ami-orchestrator'
    scrape_interval: 5s
    static_configs:
    - targets: ['localhost:5055']
    metrics_path: '/metrics'

  # Nodes production services
  - job_name: 'nodes-production'
    scrape_interval: 10s
    static_configs:
    - targets: ['localhost:8000']  # Example node service
"""

        # Store the configuration in the registry
        config_path = "launcher/production/prometheus.yml"

        # Check if configuration already exists
        try:
            existing_config = registry.get_data(config_path)
            if existing_config:
                if not confirm("Overwrite existing Prometheus configuration?", "Confirm Overwrite"):
                    return False
        except (FileNotFoundError, KeyError):
            # Config doesn't exist, which is fine
            pass

        # Store the configuration
        registry.store_data(config_path, default_config)
        return True

    except ImportError:
        return False
    except Exception:
        return False


if __name__ == "__main__":
    success = initialize_prometheus_config_in_registry()
    sys.exit(0 if success else 1)
