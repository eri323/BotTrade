"""Smoke tests de Fase 0: el esqueleto importa y la config carga con defaults seguros."""

from config.settings import settings


def test_settings_defaults():
    assert settings.PAPER is True
    assert "BTC/USD" in settings.SYMBOLS
    assert 0 < settings.MAX_POSITION_PCT <= 1
    assert 0 < settings.STOP_LOSS_PCT < 1
    assert settings.MAX_CONCURRENT_POSITIONS >= 1
    assert settings.CIRCUIT_BREAKER_DRAWDOWN_PCT > 0


def test_src_package_imports():
    import src  # noqa: F401
    import src.backtest  # noqa: F401
    import src.risk  # noqa: F401
    import src.strategy  # noqa: F401
