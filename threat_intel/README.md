# Threat Intelligence Imports

Place provider-exported CSV files here for local pre-ML screening. Files are loaded at runtime and must contain an `address` column. Recommended optional columns are `nametag`, `labels`, `labels_slug`, `reputation`, `reason`, `source`, and `decision`.

No test wallet is embedded in source code. Import only data you are licensed to use and retain its provider attribution. Etherscan Metadata and Chainabuse can also be enabled through environment settings; see `.env.example`.

For local investigation, `ENABLE_EXPLORER_REPUTATION=true` checks the public Etherscan address page for its explicit phishing/scam warning and caches the result. It is off by default so deployments can review Etherscan's current terms and choose their licensed metadata/API path.

Run `python scripts/sync_threat_intel.py` or use **Sync flagged gas users** in the local training console to refresh `data/threat_intel/etherscan_gas_guzzlers.csv`. The importer keeps only rows with an explicit phishing/scam/hack label. Presence in the high-gas table alone is never treated as malicious.
