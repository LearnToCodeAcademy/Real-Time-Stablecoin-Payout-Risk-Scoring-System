import csv

from risk_system.collector import CollectionSettings, WalletCollector


class FakeEtherscan:
    def __init__(self, *args, **kwargs):
        self.calls = 0

    def token_transfers(self, wallet, **kwargs):
        self.calls += 1
        neighbor = "0x" + f"{self.calls:040x}"
        return [
            {
                "timeStamp": "1000",
                "value": "1000000",
                "tokenDecimal": "6",
                "from": wallet,
                "to": neighbor,
            }
        ]


def test_collector_honors_target_and_writes_unlabeled_features(tmp_path, monkeypatch):
    monkeypatch.setattr("risk_system.collector.EtherscanClient", FakeEtherscan)
    seed = "0x" + "f" * 40
    collector = WalletCollector(
        CollectionSettings(
            target_wallets=3,
            tokens=["USDT"],
            seed_wallets=[seed],
            max_neighbors_per_wallet=1,
        ),
        root=tmp_path,
    )

    result = collector.run()

    assert result.status == "success"
    assert result.discovered == 3
    with collector.features_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert set(row["label"] for row in rows) == {"-1"}
