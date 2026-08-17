# Optional Deep Models

`gnn_model.py` and `deep_model.py` are research surfaces, not part of the active payout decision path. They import safely when heavy frameworks are absent and raise actionable installation errors only when a deep model is requested.

Install `requirements-deep.txt` in a separate environment. PyTorch Geometric and CUDA compatibility depends on the exact OS, Python, PyTorch, and accelerator combination, so the core/API image intentionally excludes these packages. The production path currently uses scikit-learn, XGBoost, and LightGBM artifacts because they are reproducible on CPU and supported by the version/rollback workflow.
