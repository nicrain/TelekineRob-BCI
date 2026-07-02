"""Policies package — intent inference from EEG features."""

from thymio_control.policies.alpha import AlphaPolicy
from thymio_control.policies.ei    import EiPolicy
from thymio_control.policies.tbr   import TbrPolicy

__all__ = ["AlphaPolicy", "EiPolicy", "TbrPolicy"]
