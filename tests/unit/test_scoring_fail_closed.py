import wallet_check
from risk_system.etherscan import EtherscanConfigurationError


class StubReputation:
    def __init__(self, result):
        self.result = result

    def screen(self, _address):
        return self.result


def test_reputation_match_blocks_before_transaction_fetch(monkeypatch):
    monkeypatch.setattr(
        wallet_check,
        "reputation_service",
        StubReputation(
            {
                "status": "MATCH",
                "findings": [
                    {
                        "source": "test-provider",
                        "nametag": "Reported phishing wallet",
                        "labels": ["phish-hack"],
                    }
                ],
                "providers_checked": ["test-provider"],
                "provider_errors": [],
            }
        ),
    )
    monkeypatch.setattr(
        wallet_check,
        "fetch_transactions",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )

    result = wallet_check.score_wallet_data("0x" + "3" * 40)

    assert result["decision"] == "BLOCK"
    assert result["assessment_status"] == "BLOCKED_BY_REPUTATION"


def test_provider_failure_is_unscorable_review(monkeypatch):
    monkeypatch.setattr(
        wallet_check,
        "reputation_service",
        StubReputation(
            {
                "status": "UNAVAILABLE",
                "findings": [],
                "providers_checked": [],
                "provider_errors": [],
            }
        ),
    )
    monkeypatch.setattr(
        wallet_check,
        "fetch_transactions",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(EtherscanConfigurationError("missing key")),
    )

    result = wallet_check.score_wallet_data("0x" + "4" * 40)

    assert result["decision"] == "REVIEW"
    assert result["assessment_status"] == "UNSCORABLE"
    assert result["data_status"] == "PROVIDER_UNAVAILABLE"
    assert result["prob_normal"] is None
    assert result["prob_malicious"] is None
