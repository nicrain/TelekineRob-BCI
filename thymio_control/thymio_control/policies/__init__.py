"""Policies package — intent inference from EEG features."""

from thymio_control.policies.alpha_only import AlphaOnlyPolicy
from thymio_control.policies.focus import FocusPolicy
from thymio_control.policies.theta_beta import ThetaBetaPolicy

__all__ = ["AlphaOnlyPolicy", "FocusPolicy", "ThetaBetaPolicy"]
