"""
Test the fixed decision logic.
"""


def classify_decision_old(prob_malicious, prob_poisoned, conf, features):
    """OLD LOGIC - rules first"""
    # Rules first
    if features.get("wallet_age_days", 100) <= 7:
        if prob_malicious > 0.3 or prob_poisoned > 0.2:
            return "REVIEW", "new_wallet_suspicious (rule-based check)"

    # Then model checks
    if prob_poisoned >= 0.5:
        return "BLOCK", "Poisoned wallet (address spoofing)"
    if prob_malicious >= 0.8:
        return "BLOCK", "High malicious risk"
    elif prob_malicious >= 0.5:
        return "REVIEW", "Moderate malicious risk"
    return "ALLOW", "Low risk"


def classify_decision_new(prob_malicious, prob_poisoned, conf, features):
    """NEW LOGIC - high confidence first"""
    # [CRITICAL] Check VERY HIGH model confidence FIRST
    if prob_poisoned >= 0.7:
        return "BLOCK", "Poisoned wallet (high confidence)"
    if prob_malicious >= 0.9:
        return "BLOCK", "Malicious wallet (very high confidence - phishing/scam)"

    # Then apply rules for lower confidence
    if features.get("wallet_age_days", 100) <= 7:
        if prob_malicious > 0.3 or prob_poisoned > 0.2:
            return "REVIEW", "new_wallet_suspicious (rule-based check)"

    # Then threshold checks
    if prob_poisoned >= 0.5:
        return "BLOCK", "Poisoned wallet"
    if prob_malicious >= 0.8:
        return "BLOCK", "Malicious wallet (high confidence)"
    elif prob_malicious >= 0.5:
        return "REVIEW", "Moderate malicious risk"
    return "ALLOW", "Low risk"


# Historical test used a provider-labeled phishing wallet; current tests mock the provider instead.
# Model: Malicious=0.9997, Poisoned=0.0001
features = {"wallet_age_days": 1}  # Simulating low age from cached data
prob_malicious = 0.9997
prob_poisoned = 0.0001
conf = 0.9994

print("=" * 60)
print("TEST: Provider-Labeled Phishing Wallet")
print(f"Model: Malicious={prob_malicious:.4f}, Poisoned={prob_poisoned:.4f}")
print(f"Features: wallet_age_days={features['wallet_age_days']}")
print("=" * 60)

old_decision, old_reason = classify_decision_old(prob_malicious, prob_poisoned, conf, features)
new_decision, new_reason = classify_decision_new(prob_malicious, prob_poisoned, conf, features)

print(f"\nOLD LOGIC: {old_decision} ({old_reason})")
print(f"NEW LOGIC: {new_decision} ({new_reason})")

if old_decision == "REVIEW" and new_decision == "BLOCK":
    print("\n[OK] FIX WORKING - Now correctly blocks high-confidence malicious wallets!")
else:
    print("\n[WARN] Fix may not be working as expected")
