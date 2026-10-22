"""Proposed new opt-in installer; root owns common migrations.py wiring."""
from ..resources import schema_path
from .migrations import install_worker_liveness, _install_component


def install_worker_custody(engine):
    install_worker_liveness(engine)
    _install_component(engine, schema_path('migration_034.sql'), 34, 33, 'worker_custody_interface')
    from ..workspaces.worker_custody import verify_worker_custody
    verify_worker_custody(engine)
