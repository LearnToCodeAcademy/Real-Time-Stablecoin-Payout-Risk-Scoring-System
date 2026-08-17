import pandas as pd

from risk_system.training import _split_data, load_training_data


def test_repository_training_data_is_wallet_deduplicated():
    data, info = load_training_data("usdt")

    assert data["wallet"].is_unique
    assert info["usable_unique_wallets"] == len(data)
    assert set(data["label"]) == {0, 1, 2}


def test_split_has_no_wallet_overlap():
    rows = []
    for label in (0, 1, 2):
        for index in range(30):
            rows.append({"wallet": f"0x{label:01x}{index:039x}", "label": label})
    data = pd.DataFrame(rows)

    splits = _split_data(data, seed=42)
    train = set(splits["train"]["wallet"])
    validation = set(splits["validation"]["wallet"])
    test = set(splits["test"]["wallet"])

    assert train.isdisjoint(validation)
    assert train.isdisjoint(test)
    assert validation.isdisjoint(test)
