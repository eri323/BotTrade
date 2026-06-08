"""Tests del wrapper de Alpaca (src/execution/broker.py) — siempre con mocks.

Nunca se llama al API real.
"""

from alpaca.common.exceptions import APIError

from src.execution.broker import Broker


def test_buy_submits_market_order(mock_trading_client):
    """Sin posición previa, buy() envía una orden de mercado con los params correctos."""
    broker = Broker(client=mock_trading_client)
    broker.buy("BTC/USD", notional=500.0)

    mock_trading_client.submit_order.assert_called_once()
    order = mock_trading_client.submit_order.call_args[0][0]
    assert order.symbol == "BTC/USD"
    assert float(order.notional) == 500.0


def test_buy_skips_when_position_exists(mock_trading_client, mocker):
    """Si ya hay posición abierta, no se envía otra orden (idempotencia)."""
    mock_trading_client.get_open_position.side_effect = None
    mock_trading_client.get_open_position.return_value = mocker.MagicMock(symbol="BTC/USD")

    broker = Broker(client=mock_trading_client)
    result = broker.buy("BTC/USD", notional=500.0)

    assert result is None
    mock_trading_client.submit_order.assert_not_called()


def test_buy_handles_api_error_gracefully(mock_trading_client):
    """Un error del API no debe crashear el bot: buy() retorna None."""
    mock_trading_client.submit_order.side_effect = APIError(
        '{"code": 50010000, "message": "internal server error"}'
    )

    broker = Broker(client=mock_trading_client)
    result = broker.buy("BTC/USD", notional=500.0)

    assert result is None


def test_get_position_returns_none_when_absent(mock_trading_client):
    """Sin posición, get_position() devuelve None en vez de propagar la excepción."""
    broker = Broker(client=mock_trading_client)
    assert broker.get_position("BTC/USD") is None


def test_get_position_returns_position_when_present(mock_trading_client, mocker):
    mock_trading_client.get_open_position.side_effect = None
    pos = mocker.MagicMock(symbol="BTC/USD")
    mock_trading_client.get_open_position.return_value = pos

    broker = Broker(client=mock_trading_client)
    assert broker.get_position("BTC/USD") is pos


def test_get_account_passthrough(mock_trading_client):
    broker = Broker(client=mock_trading_client)
    account = broker.get_account()
    assert account.cash == "10000.00"


def test_close_position_calls_client(mock_trading_client):
    broker = Broker(client=mock_trading_client)
    broker.close_position("BTC/USD")
    mock_trading_client.close_position.assert_called_once_with("BTC/USD")


def test_close_position_handles_api_error(mock_trading_client):
    mock_trading_client.close_position.side_effect = APIError('{"message": "no position"}')
    broker = Broker(client=mock_trading_client)
    assert broker.close_position("BTC/USD") is None
