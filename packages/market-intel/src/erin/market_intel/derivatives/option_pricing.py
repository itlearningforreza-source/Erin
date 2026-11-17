"""Option Pricing Engine - Derivatives valuation and Greeks."""

from .analytics import (
    Option, OptionType, OptionStyle, Greeks,
    BlackScholesMerton, BinomialTree, MonteCarloPricer, VolatilitySurface
)

# Re-export key classes with expected names
OptionPricingEngine = BlackScholesMerton

__all__ = [
    'Option',
    'OptionType',
    'OptionStyle',
    'Greeks',
    'BlackScholesMerton',
    'BinomialTree',
    'MonteCarloPricer',
    'VolatilitySurface',
    'OptionPricingEngine',
    'create_bsm_pricer',
    'create_binomial_pricer',
    'create_mc_pricer',
    'create_vol_surface',
]