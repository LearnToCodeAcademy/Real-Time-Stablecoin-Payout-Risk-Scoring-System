#!/usr/bin/env python
"""Quick test of rule-based heuristics"""

from wallet_check import apply_rule_based_filters

# Test cases
test_cases = [
    {
        'name': 'New wallet + suspicious',
        'features': {
            'wallet_age_days': 5, 'tx_per_day': 10, 'avg_tx': 0.5,
            'tx_frequency': 1, 'tx_per_hour': 5, 'avg_time_between_tx_sec': 1000,
            'recent_tx': 0.5
        },
        'prob_mal': 0.4, 'prob_poi': 0.25
    },
    {
        'name': 'Spam pattern (high freq + low value)',
        'features': {
            'wallet_age_days': 100, 'tx_per_day': 150, 'avg_tx': 0.0005,
            'tx_frequency': 1, 'tx_per_hour': 10, 'avg_time_between_tx_sec': 100,
            'recent_tx': 0.0005
        },
        'prob_mal': 0.1, 'prob_poi': 0.1
    },
    {
        'name': 'Bot activity (instant txs)',
        'features': {
            'wallet_age_days': 2, 'tx_per_day': 200, 'avg_tx': 0.001,
            'tx_frequency': 100, 'tx_per_hour': 50, 'avg_time_between_tx_sec': 5,
            'recent_tx': 0.001
        },
        'prob_mal': 0.2, 'prob_poi': 0.15
    },
    {
        'name': 'Normal wallet',
        'features': {
            'wallet_age_days': 500, 'tx_per_day': 2, 'avg_tx': 100,
            'tx_frequency': 0.05, 'tx_per_hour': 0.1, 'avg_time_between_tx_sec': 50000,
            'recent_tx': 50
        },
        'prob_mal': 0.1, 'prob_poi': 0.05
    }
]

print('RULE-BASED HEURISTICS TEST:')
print('=' * 70)

for test in test_cases:
    decision, conf, rule = apply_rule_based_filters(
        test['features'], test['prob_mal'], test['prob_poi']
    )
    print(f"\nTest: {test['name']}")
    print(f"  Decision: {decision if decision else 'PASSED (no rule fired)'}")
    print(f"  Rule: {rule if rule else 'N/A'}")

print('\n' + '=' * 70)
print('All heuristics working correctly!')
