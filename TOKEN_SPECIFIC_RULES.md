# Token-Specific Scoring & Training Configuration

## Architecture Overview

Your system now uses **token-specific configurations** for completely different attacker behaviors:

```
main.py (All 54 tokens)
  ├── Generates CSVs for ALL tokens
  └── train_ml.py & wallet_check.py process EACH token with unique rules

train_ml.py (Token-Specific Training)
  ├── USDT: Institutional phishing patterns
  ├── USDC: Retail social engineering patterns  
  ├── DAI: DeFi exploit patterns
  ├── BUSD: Exchange manipulation patterns
  ├── USDP: Regulatory evasion patterns
  └── TUSD: Bridge exploit patterns

wallet_check.py (Token-Specific Scoring)
  ├── Each token has different risk thresholds
  ├── Each token has different detection rules
  ├── Each token has different primary threats
  └── Each token uses different feature importance weights
```

## Implementation Details

### 1. train_ml.py - Token-Specific Training Configuration

```python
TOKEN_CONFIG = {
    "usdt": {
        "name": "Tether USD",
        "primary_threats": ["institutional_phishing", "credential_theft"],
        "class_weights": {0: 0.8, 1: 6.0, 2: 4.0},  # Higher weight for malicious
        "high_confidence_threshold": 0.95,  # Very strict for USDT
        "feature_importance": ["avg_tx", "tx_frequency", "wallet_age_days"],
    },
    "dai": {
        "name": "DAI (DeFi)",
        "primary_threats": ["flash_loan_exploits", "collateral_manipulation"],
        "class_weights": {0: 0.8, 1: 5.5, 2: 4.0},  # Different weights
        "high_confidence_threshold": 0.92,  # Slightly less strict
        "feature_importance": ["dust_tx_ratio", "is_poisoned_pattern", "avg_tx"],
    },
    # ... each token has unique config
}
```

**What This Means:**
- USDT training focuses on institutional patterns (large TXs, credential theft)
- DAI training focuses on DeFi patterns (flash loans, collateral) 
- PEPE (meme coins) would focus on rug pulls, fake launches
- Each token's ML model learns different patterns because attackers use token-specific tactics

### 2. wallet_check.py - Token-Specific Scoring Rules

```python
TOKEN_SCORING_RULES = {
    "USDT": {
        "risk_profile": "HIGH_VALUE_TARGETS",
        "malicious_threshold": 0.88,  # Higher threshold = more strict
        "poisoned_threshold": 0.75,
        "rule_checks": ["large_tx_spike", "unusual_institution_pattern"],
        "anomaly_window_hours": 24,  # Institutional attacks = longer window
    },
    "DAI": {
        "risk_profile": "DEFI_EXPLOITS",
        "malicious_threshold": 0.82,  # Lower threshold = less strict
        "poisoned_threshold": 0.70,
        "rule_checks": ["flash_loan_patterns", "collateral_manipulation"],
        "anomaly_window_hours": 1,  # DeFi attacks = instant detection
    },
    # ... each token has unique scoring rules
}
```

**What This Means:**
- USDT requires 88% confidence (institutional = high bar)
- DAI requires 82% confidence (DeFi = lower bar)
- USDT anomaly window = 24 hours (institutional attacks plot over time)
- DAI anomaly window = 1 hour (flash loan attacks are instant)

### 3. How Scoring Works Per Token

```python
def classify_decision(prob_malicious, prob_poisoned, conf, features, token="USDT"):
    # Get TOKEN-SPECIFIC thresholds
    rules = TOKEN_SCORING_RULES[token]
    malicious_thresh = rules["malicious_threshold"]  # 0.88 for USDT, 0.82 for DAI
    
    # Apply token-specific logic
    if prob_malicious >= malicious_thresh:
        return "BLOCK, f"Malicious {token} wallet - {rules['risk_profile']}"
    
    # Different tokens = different messages with threat context
```

**Real-World Example:**

| Scenario | USDT | DAI | PEPE |
|----------|------|-----|------|
| 85% confidence malicious | REVIEW | BLOCK | REVIEW |
| Large TX spike | Alert (institutional) | Ignore (normal DeFi) | Suspicious (whale pump) |
| Many small TXs | Normal (retail) | Flash loan risk | Rug pull setup |
| New wallet | REVIEW | REVIEW | BLOCK (pump & dump) |

## Why Token-Specific Rules?

### USDT (Institutional Stablecoin)
- Attackers: Credential theft, fake documents
- Pattern: Large value, slow execution (24hr+ plots)
- Threshold: 88% (must be very sure)
- Features: `avg_tx`, `tx_frequency`, `wallet_age_days`

### DAI (DeFi Token)
- Attackers: Flash loan exploits, governance hacks
- Pattern: High frequency, complex interactions, instant
- Threshold: 82% (DeFi is volatile)
- Features: `dust_tx_ratio`, `is_poisoned_pattern`, collateral tracking

### PEPE (Meme Token)
- Attackers: Rug pulls, fake launches
- Pattern: Sudden volume spike right before crash
- Threshold: 75% (high false positive rate)
- Features: Price action, velocity, holder concentration

## Using Token-Specific Configuration

### Training with Token-Specific Rules

```python
# train_ml.py automatically uses TOKEN_CONFIG
python train_ml.py  # Uses USDT token config by default

# Or train specific tokens  
python train_ml.py --tokens dai,usdc  # Uses DAI and USDC configs
```

The trainer will:
1. Load config for each token
2. Apply token-specific class weights
3. Learn token-specific feature importance
4. Save models that understand token patterns

### Scoring with Token-Specific Rules

```python
# wallet_check.py automatically uses TOKEN_SCORING_RULES
python wallet_check.py

# For USDT wallet:
Token: USDT
Malicious confidence: 87%
Threshold: 88%
Result: REVIEW (just below threshold due to USDT's strict rules)

# For DAI wallet with same 87% confidence:
Token: DAI
Malicious confidence: 87%
Threshold: 82%
Result: BLOCK (exceeds DAI's threshold)

# Same confidence, different decision = CORRECT behavior!
```

## Attacker Profiles Per Token

### USDT (Tether) - High Value Attacks
```
Threat: Credential phishing
Pattern: Slow, institutional, large amounts
Detection: wallet_age_days, avg_tx, institution patterns
Counter: High thresholds, 24hr monitoring
```

### USDC (USD Coin) - Retail Phishing
```
Threat: Social engineering
Pattern: Multiple small attempts, rapid
Detection: social_engineering_signature, fake_contracts
Counter: Medium thresholds, 6hr windows
```

### DAI (DeFi) - Protocol Exploits  
```
Threat: Flash loan attacks, collateral manipulation
Pattern: High frequency, complex txs, instant
Detection: dust_tx_ratio, is_poisoned_pattern
Counter: Low thresholds, 1hr windows
```

### BUSD (Binance USD) - Exchange Attacks
```
Threat: Wash trading, margin attacks, arb manipulation
Pattern: Patterns correlated with order books
Detection: exchange_arb_wash, institutional_spoofing
Counter: Medium thresholds, 12hr windows
```

## Key Benefits

✅ **Accuracy**: Each token's unique patterns learned separately  
✅ **Flexibility**: Different thresholds per token type  
✅ **Scalability**: Easy to add new tokens with own configs  
✅ **Transparency**: Clear why different decisions for similar confidence  
✅ **Optimization**: Each model optimized for its token's threat landscape  

## Next Steps

1. **Verify Training**: Run `python train_ml.py` with token configs
2. **Test Scoring**: Score wallets of different tokens, see different thresholds
3. **Monitor Results**: Track token-specific false positives/negatives
4. **Tune Configs**: Adjust thresholds based on real-world performance
5. **Add Tokens**: New trained tokens get own TOKEN_CONFIG entries

---

**Your system now treats each token as a unique security challenge—because attackers do the same!** 🎯
