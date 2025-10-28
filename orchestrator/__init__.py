"""
Pipeline modules for the Dungeon Master's Companion orchestrator.

The package exposes the high-level `Orchestrator` class as the primary entry
point. Stage-specific helpers are intentionally kept small so the pipeline can
be reused in interactive shells, notebooks, or future services.
"""

from .pipeline import Orchestrator

__all__ = ["Orchestrator"]
