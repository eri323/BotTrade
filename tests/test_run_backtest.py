"""Test del path de graficado del CLI de backtest (scripts/run_backtest.py)."""

from scripts.run_backtest import _plot
from src.backtest.compare import run_comparison


def test_plot_creates_nonempty_file(tmp_path, sample_ohlcv):
    out = run_comparison(sample_ohlcv, initial_capital=10_000.0)
    path = tmp_path / "bt.png"
    _plot(sample_ohlcv, out["results"], str(path))
    assert path.exists()
    assert path.stat().st_size > 0
