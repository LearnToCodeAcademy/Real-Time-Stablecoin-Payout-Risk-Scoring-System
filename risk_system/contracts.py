"""Canonical Ethereum token metadata used by collectors and live streams."""

from __future__ import annotations

from typing import TypedDict


class TokenMetadata(TypedDict):
    address: str
    decimals: int


TOKEN_CONTRACTS: dict[str, TokenMetadata] = {
    "USDT": {"address": "0xdac17f958d2ee523a2206206994597c13d831ec7", "decimals": 6},
    "USDC": {"address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "decimals": 6},
    "BUSD": {"address": "0x4fabb145d64652a948d72533023f6e7a623c7c53", "decimals": 18},
    "DAI": {"address": "0x6b175474e89094c44da98b954eedeac495271d0f", "decimals": 18},
    "USDP": {"address": "0x8e870d67f660d95d5be2d627f142b3d3c9145e9", "decimals": 18},
    "TUSD": {"address": "0x0000000000085d4780b73119b8b580991dee8d52", "decimals": 18},
}

CONTRACT_TO_TOKEN = {metadata["address"].lower(): token for token, metadata in TOKEN_CONTRACTS.items()}

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
