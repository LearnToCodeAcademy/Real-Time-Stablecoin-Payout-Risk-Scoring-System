from risk_system.features import FEATURE_COLUMNS, features_from_transfers


def test_features_use_canonical_schema():
    wallet = "0x" + "a" * 40
    recipient = "0x" + "b" * 40
    transfers = [
        {
            "timeStamp": "1000",
            "value": "1000000",
            "tokenDecimal": "6",
            "from": wallet,
            "to": recipient,
        },
        {
            "timeStamp": "1060",
            "value": "2000000",
            "tokenDecimal": "6",
            "from": recipient,
            "to": wallet,
        },
        {
            "timeStamp": "1120",
            "value": "500",
            "tokenDecimal": "6",
            "from": wallet,
            "to": recipient,
        },
    ]

    features = features_from_transfers(transfers, wallet)

    assert list(features) == FEATURE_COLUMNS
    assert features["tx_frequency"] == 3
    assert features["avg_time_between_tx_sec"] == 60
    assert features["tiny_tx_count"] == 1
    assert features["unique_receivers"] == 1
