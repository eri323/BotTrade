"""Wrapper de Alpaca — ÚNICA capa del proyecto que conoce el broker.

Abstrae paper vs live mediante el flag PAPER. Métodos: submit_order/buy,
get_position, get_account, close_position. Idempotencia: no duplicar órdenes.

TODO (Fase 2): implementar Broker sobre TradingClient. Ver skill `alpaca-integration`.
"""
