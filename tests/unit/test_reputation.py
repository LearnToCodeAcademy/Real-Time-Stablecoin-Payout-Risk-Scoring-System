from risk_system.reputation import ReputationService, sync_etherscan_gas_guzzler_labels


def test_local_reputation_feed_matches_without_source_code_address(tmp_path, monkeypatch):
    address = "0x" + "1" * 40
    feed = tmp_path / "provider-export.csv"
    feed.write_text(
        "address,nametag,labels,reputation,source,reason\n"
        f"{address},Reported Wallet,phish-hack,2,provider-export,Verified phishing report\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("THREAT_INTEL_FILES", str(feed))

    result = ReputationService().screen(address)

    assert result["status"] == "MATCH"
    assert result["findings"][0]["source"] == "provider-export"


def test_no_feed_is_unavailable_not_clear(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("THREAT_INTEL_FILES", raising=False)
    monkeypatch.delenv("CHAINABUSE_API_USERNAME", raising=False)
    monkeypatch.delenv("CHAINABUSE_API_PASSWORD", raising=False)
    monkeypatch.setenv("ENABLE_ETHERSCAN_METADATA", "false")

    result = ReputationService().screen("0x" + "2" * 40)

    assert result["status"] == "UNAVAILABLE"
    assert not result["findings"]


def test_malformed_local_feed_is_ignored(monkeypatch, tmp_path):
    feed = tmp_path / "not-a-threat-feed.csv"
    feed.write_text("name,value\nexample,1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("THREAT_INTEL_FILES", str(feed))
    monkeypatch.setenv("ENABLE_ETHERSCAN_METADATA", "false")
    monkeypatch.setenv("ENABLE_EXPLORER_REPUTATION", "false")

    result = ReputationService().screen("0x" + "9" * 40)

    assert result["status"] == "UNAVAILABLE"
    assert not result["findings"]


def test_explorer_parser_uses_explicit_warning_without_address_fixture(monkeypatch, tmp_path):
    class Response:
        text = (
            "<html><head><title>Fake_Phishing123 | Address</title></head>"
            "<body>There are reports that this address was used in a Phishing scam. Phish / Hack</body></html>"
        )

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENABLE_EXPLORER_REPUTATION", "true")
    monkeypatch.delenv("THREAT_INTEL_FILES", raising=False)
    monkeypatch.setattr("risk_system.reputation.requests.get", lambda *_args, **_kwargs: Response())

    result = ReputationService().screen("0x" + "5" * 40)

    assert result["status"] == "MATCH"
    assert result["findings"][0]["source"] == "etherscan_public_label"


def test_explorer_ignores_risky_counterparty_in_transaction_table(monkeypatch, tmp_path):
    class Response:
        text = (
            "<html><head><title>Ordinary Wallet | Address</title></head>"
            "<body><table><tr><td>Fake_Phishing999 transferred dust to this wallet</td></tr></table></body></html>"
        )

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENABLE_EXPLORER_REPUTATION", "true")
    monkeypatch.delenv("THREAT_INTEL_FILES", raising=False)
    monkeypatch.setattr("risk_system.reputation.requests.get", lambda *_args, **_kwargs: Response())

    result = ReputationService().screen("0x" + "8" * 40)

    assert result["status"] == "CLEAR"
    assert not result["findings"]


def test_gas_guzzler_sync_imports_only_explicit_risk_rows(monkeypatch, tmp_path):
    risky = "0x" + "6" * 40
    ordinary = "0x" + "7" * 40

    class Response:
        text = (
            "<table>"
            f'<tr><td><a href="/address/{risky}">Fake_Phishing42</a></td></tr>'
            f'<tr><td><a href="/address/{ordinary}">Ordinary Contract</a></td></tr>'
            "</table>"
        )

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr("risk_system.reputation.requests.get", lambda *_args, **_kwargs: Response())
    output = tmp_path / "labels.csv"

    result = sync_etherscan_gas_guzzler_labels(output)

    assert result["records"] == 1
    contents = output.read_text(encoding="utf-8")
    assert risky in contents
    assert ordinary not in contents
