"""Standalone entry point for the real blockchain live-event service."""

from __future__ import annotations

import asyncio
import json
import logging

from risk_system.live import AlertStore, LiveEventBroker
from wallet_check import score_wallet_data

logging.basicConfig(level=logging.INFO)


def score_live_wallet(wallet: str, token: str):
    return score_wallet_data(wallet, manual_token=token)


async def run_stream_listener() -> None:
    store = AlertStore()
    broker = LiveEventBroker(store, scorer=score_live_wallet)
    queue = broker.subscribe()
    await broker.start()
    print(json.dumps({"status": broker.status}, indent=2))
    try:
        while True:
            event = await queue.get()
            print(json.dumps(event, default=str))
    finally:
        broker.unsubscribe(queue)
        await broker.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_stream_listener())
    except KeyboardInterrupt:
        pass
