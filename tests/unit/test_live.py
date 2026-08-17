from risk_system.contracts import TOKEN_CONTRACTS, TRANSFER_TOPIC
from risk_system.live import AlertStore, LiveEventBroker


def test_token_contract_addresses_are_valid_ethereum_addresses():
    for metadata in TOKEN_CONTRACTS.values():
        address = metadata["address"]
        assert address.startswith("0x")
        assert len(address) == 42
        int(address[2:], 16)


def _topic(address: str) -> str:
    return "0x" + "0" * 24 + address[2:]


def test_real_log_parser_extracts_transfer_fields():
    sender = "0x" + "1" * 40
    recipient = "0x" + "2" * 40
    log = {
        "address": TOKEN_CONTRACTS["USDT"]["address"],
        "topics": [TRANSFER_TOPIC, _topic(sender), _topic(recipient)],
        "data": hex(12_500_000),
        "transactionHash": "0x" + "3" * 64,
        "logIndex": "0x4",
        "blockNumber": "0x10",
        "timeStamp": "0x64",
    }

    event = LiveEventBroker._parse_log(log, "etherscan")

    assert event is not None
    assert event["verified_real"] is True
    assert event["wallet"] == recipient
    assert event["token"] == "USDT"
    assert event["amount"] == 12.5
    assert event["block_number"] == 16
    assert event["decision"] == "OBSERVED"


def test_alert_store_unifies_risk_events_and_cases(tmp_path):
    store = AlertStore(tmp_path / "alerts.db")
    event = store.add_event(
        {
            "event_id": "tx:1",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "wallet": "0x" + "a" * 40,
            "token": "USDT",
            "decision": "BLOCK",
            "score": 0.97,
            "source": "etherscan",
            "verified_real": True,
        }
    )

    assert event["decision"] == "BLOCK"
    assert store.recent_events()[0]["verified_real"] is True
    assert store.cases(status="open")[0]["event_id"] == "tx:1"
