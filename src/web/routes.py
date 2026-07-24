"""Endpoints JSON del dashboard. Solo leen Broker y Repository; no operan el mercado."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.backtest.metrics import live_summary
from src.execution.broker import Broker
from src.persistence.repository import Repository
from src.web.bot_manager import BotManager
from src.web.deps import get_broker, get_manager, get_repository

router = APIRouter()


@router.get("/status")
def status(manager: BotManager = Depends(get_manager)) -> dict:
    return manager.status()


@router.post("/start")
def start(confirm_live: bool = False, manager: BotManager = Depends(get_manager)) -> dict:
    try:
        return manager.start(confirm_live=confirm_live)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.post("/stop")
def stop(close_positions: bool = False, manager: BotManager = Depends(get_manager)) -> dict:
    return manager.stop(close_positions=close_positions)


@router.get("/account")
def account(broker: Broker = Depends(get_broker)) -> dict:
    acct = broker.get_account()
    portfolio_value = float(acct.portfolio_value)
    return {
        "portfolio_value": portfolio_value,
        "cash": float(acct.cash),
        "last_equity": float(getattr(acct, "last_equity", None) or portfolio_value),
    }


@router.get("/positions")
def positions(broker: Broker = Depends(get_broker)) -> list[dict]:
    return [
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry_price": float(p.avg_entry_price),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
        }
        for p in broker.list_positions()
    ]


@router.get("/trades")
def trades(repo: Repository = Depends(get_repository)) -> list[dict]:
    return repo.get_trades()


@router.get("/equity")
def equity(repo: Repository = Depends(get_repository)) -> list[dict]:
    return repo.get_daily_metrics()


@router.get("/metrics")
def metrics(repo: Repository = Depends(get_repository)) -> dict:
    portfolio_values = [m["portfolio_value"] for m in repo.get_daily_metrics()]
    return live_summary(repo.get_trades(), portfolio_values)
