"""Leakage-safe, versioned model training and rollback services."""

from __future__ import annotations

import json
import math
import os
import pickle
import shutil
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    make_scorer,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, label_binarize

from .features import FEATURE_COLUMNS

try:
    from xgboost import XGBClassifier as _XGBModel

    XGBModel: Any = _XGBModel
    HAS_XGB = True
except ImportError:
    XGBModel = None
    HAS_XGB = False

try:
    from lightgbm import LGBMClassifier as _LGBModel

    LGBModel: Any = _LGBModel
    HAS_LGB = True
except ImportError:
    LGBModel = None
    HAS_LGB = False

try:
    import optuna as _optuna

    optuna: Any = _optuna
    HAS_OPTUNA = True
except ImportError:
    optuna = None
    HAS_OPTUNA = False


TRAINABLE_TOKENS = ("usdt", "usdc", "busd", "dai", "usdp", "tusd")
CLASS_NAMES = {0: "safe", 1: "malicious", 2: "poisoned"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class TrainingOptions:
    token: str = "usdt"
    model: str = "auto"
    random_seed: int = 42
    estimators: int = 300
    max_depth: int | None = 16
    cv_folds: int = 5
    tuning_trials: int = 0

    def validate(self) -> None:
        self.token = self.token.lower().strip()
        self.model = self.model.lower().strip()
        if self.token not in {*TRAINABLE_TOKENS, "all"}:
            raise ValueError(f"Unsupported token: {self.token}")
        if self.model not in {"auto", "rf", "xgb", "lgb"}:
            raise ValueError(f"Unsupported model: {self.model}")
        if self.estimators < 50 or self.estimators > 5000:
            raise ValueError("estimators must be between 50 and 5,000")
        if self.cv_folds < 2 or self.cv_folds > 10:
            raise ValueError("cv_folds must be between 2 and 10")
        if self.tuning_trials < 0 or self.tuning_trials > 200:
            raise ValueError("tuning_trials must be between 0 and 200")


@dataclass
class TrainingRun:
    run_id: str
    status: str
    token: str
    model: str
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    progress: float = 0.0
    stage: str = "queued"
    metrics: dict[str, Any] = field(default_factory=dict)
    versions: dict[str, str] = field(default_factory=dict)
    message: str = "Queued"


class TrainingDataError(RuntimeError):
    """Raised when the available labels cannot support honest evaluation."""


def _candidate_paths(token: str) -> list[Path]:
    names = [
        f"{token}_training_ready.csv",
        f"v0_{token}.csv",
        f"v1_{token}.csv",
        f"v2_{token}.csv",
        f"v3_clean_{token}.csv",
        f"{token}_labeled_v3.csv",
        f"{token}_labeled_v4.csv",
        f"v4_{token}.csv",
    ]
    paths: list[Path] = []
    for root in (Path("datasets"), Path("datasets deprecated")):
        for name in names:
            candidate = root / name
            if candidate.exists() and candidate.stat().st_size > 0:
                paths.append(candidate)
    paths.extend(sorted(Path("data/collections").glob("*/features.csv")))
    return paths


def load_training_data(token: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load trusted labels, remove conflicts, and keep one row per wallet."""
    frames: list[pd.DataFrame] = []
    sources: list[str] = []
    for path in _candidate_paths(token):
        try:
            frame = pd.read_csv(path)
        except (pd.errors.EmptyDataError, OSError):
            continue
        if "label" not in frame or "wallet" not in frame:
            continue
        frame = frame.copy()
        if "token" in frame:
            frame = frame[frame["token"].astype(str).str.lower() == token].copy()
            if frame.empty:
                continue
        frame["source_file"] = str(path)
        frames.append(frame)
        sources.append(str(path))
    if not frames:
        raise TrainingDataError(f"No labeled dataset files were found for {token.upper()}")

    data = pd.concat(frames, ignore_index=True, sort=False)
    data["wallet"] = data["wallet"].astype(str).str.lower().str.strip()
    data["label"] = pd.to_numeric(data["label"], errors="coerce")
    data = data[data["label"].isin(CLASS_NAMES)].copy()
    data["label"] = data["label"].astype(int)
    data = data[data["wallet"].str.match(r"^0x[a-f0-9]{40}$", na=False)]
    for feature in FEATURE_COLUMNS:
        if feature not in data:
            data[feature] = 0.0
        data[feature] = (
            pd.to_numeric(data[feature], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
        )

    labels_per_wallet = data.groupby("wallet")["label"].nunique()
    conflicting_wallets = set(labels_per_wallet[labels_per_wallet > 1].index)
    if conflicting_wallets:
        data = data[~data["wallet"].isin(conflicting_wallets)]
    data = data.sort_values("source_file").drop_duplicates("wallet", keep="last")
    class_counts = {
        str(int(key)): int(value) for key, value in data["label"].value_counts().sort_index().items()
    }
    missing_classes = sorted(set(CLASS_NAMES) - set(data["label"].unique()))
    if missing_classes:
        readable = ", ".join(CLASS_NAMES[value] for value in missing_classes)
        raise TrainingDataError(
            f"{token.upper()} is missing labeled classes: {readable}. "
            f"Current class counts: {class_counts}. Collection may add wallets, but trusted labels are still required."
        )
    smallest_class = int(data["label"].value_counts().min())
    if smallest_class < 10:
        raise TrainingDataError(
            f"{token.upper()} has only {smallest_class} rows in its smallest class; "
            "at least 10 are required for a separated test set."
        )
    return data.reset_index(drop=True), {
        "source_files": sources,
        "raw_rows": int(sum(len(frame) for frame in frames)),
        "usable_unique_wallets": int(len(data)),
        "conflicting_wallets_dropped": int(len(conflicting_wallets)),
        "class_counts": class_counts,
    }


def _split_data(data: pd.DataFrame, seed: int) -> dict[str, Any]:
    train_val, test = train_test_split(
        data,
        test_size=0.15,
        stratify=data["label"],
        random_state=seed,
    )
    train, validation = train_test_split(
        train_val,
        test_size=0.1764705882,
        stratify=train_val["label"],
        random_state=seed,
    )
    return {
        "train": train.reset_index(drop=True),
        "validation": validation.reset_index(drop=True),
        "test": test.reset_index(drop=True),
    }


def _models(options: TrainingOptions) -> dict[str, Any]:
    candidates: dict[str, Any] = {
        "rf": RandomForestClassifier(
            n_estimators=options.estimators,
            max_depth=options.max_depth,
            min_samples_split=4,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=options.random_seed,
            n_jobs=int(os.getenv("TRAIN_N_JOBS", "-1")),
        )
    }
    candidates["rf_recall"] = RandomForestClassifier(
        n_estimators=options.estimators,
        max_depth=options.max_depth,
        min_samples_split=4,
        min_samples_leaf=1,
        class_weight={0: 1.0, 1: 8.0, 2: 4.0},
        random_state=options.random_seed,
        n_jobs=int(os.getenv("TRAIN_N_JOBS", "-1")),
    )
    if HAS_XGB:
        candidates["xgb"] = XGBModel(
            n_estimators=options.estimators,
            max_depth=6 if options.max_depth is None else min(options.max_depth, 12),
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            objective="multi:softprob",
            eval_metric="mlogloss",
            random_state=options.random_seed,
            n_jobs=int(os.getenv("TRAIN_N_JOBS", "-1")),
        )
    if HAS_LGB:
        candidates["lgb"] = LGBModel(
            n_estimators=options.estimators,
            learning_rate=0.05,
            num_leaves=31,
            class_weight="balanced",
            random_state=options.random_seed,
            n_jobs=int(os.getenv("TRAIN_N_JOBS", "-1")),
            verbosity=-1,
        )
        candidates["lgb_recall"] = LGBModel(
            n_estimators=options.estimators,
            learning_rate=0.04,
            num_leaves=24,
            min_child_samples=10,
            class_weight={0: 1.0, 1: 8.0, 2: 4.0},
            random_state=options.random_seed,
            n_jobs=int(os.getenv("TRAIN_N_JOBS", "-1")),
            verbosity=-1,
        )
    if options.model == "auto":
        return candidates
    if options.model not in candidates:
        raise TrainingDataError(f"Requested model '{options.model}' is not installed")
    return {options.model: candidates[options.model]}


def _distribution(frame: pd.DataFrame) -> dict[str, int]:
    return {
        CLASS_NAMES[int(label)]: int(count)
        for label, count in frame["label"].value_counts().sort_index().items()
    }


def _safe_roc_auc(model: Any, x_test: np.ndarray, y_test: pd.Series) -> dict[str, float | None]:
    if not hasattr(model, "predict_proba"):
        return {name: None for name in CLASS_NAMES.values()}
    probabilities = model.predict_proba(x_test)
    classes = [int(value) for value in model.classes_]
    binary = label_binarize(y_test, classes=[0, 1, 2])
    result: dict[str, float | None] = {}
    for label in CLASS_NAMES:
        if label not in classes or binary[:, label].min() == binary[:, label].max():
            result[CLASS_NAMES[label]] = None
            continue
        column = classes.index(label)
        result[CLASS_NAMES[label]] = float(roc_auc_score(binary[:, label], probabilities[:, column]))
    return result


def _markdown_report(token: str, version: str, metrics: dict[str, Any]) -> str:
    report = metrics["classification_report"]
    target_met = (
        metrics["test_macro_f1"] >= 0.9
        and metrics["malicious_recall"] >= 0.9
        and metrics["poisoned_recall"] >= 0.9
    )
    rows = [
        f"# {token.upper()} Model Performance",
        "",
        f"Model version: `{version}`",
        "",
        "> Generated by `risk_system.training`; numbers are from the untouched wallet-level test set.",
        "",
        "## Summary",
        "",
        f"- Selected model: `{metrics['selected_model']}`",
        f"- Test macro F1: `{metrics['test_macro_f1']:.4f}`",
        f"- Test accuracy: `{metrics['test_accuracy']:.4f}`",
        f"- Malicious recall: `{metrics['malicious_recall']:.4f}`",
        f"- Poisoned recall: `{metrics['poisoned_recall']:.4f}`",
        f"- Cross-validation macro F1: `{metrics['cv_macro_f1_mean']:.4f} +/- {metrics['cv_macro_f1_std']:.4f}`",
        f"- Hyperparameter trials: `{metrics.get('tuning', {}).get('completed_trials', 0)}`",
        f"- Safety target status: `{'MET' if target_met else 'NOT MET'}`",
        "",
        "## Splits",
        "",
        "| Split | Wallets | Distribution |",
        "|---|---:|---|",
    ]
    for split_name, details in metrics["splits"].items():
        rows.append(
            f"| {split_name.title()} | {details['rows']} | `{json.dumps(details['distribution'], sort_keys=True)}` |"
        )
    rows.extend(
        [
            "",
            "## Per-Class Results",
            "",
            "| Class | Precision | Recall | F1 | Support | ROC-AUC |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for class_name in CLASS_NAMES.values():
        values = report[class_name]
        auc = metrics["roc_auc_ovr"].get(class_name)
        auc_text = "n/a" if auc is None else f"{auc:.4f}"
        rows.append(
            f"| {class_name.title()} | {values['precision']:.4f} | {values['recall']:.4f} | "
            f"{values['f1-score']:.4f} | {int(values['support'])} | {auc_text} |"
        )
    rows.extend(
        [
            "",
            "## Confusion Matrix",
            "",
            "Rows are actual labels; columns are predicted labels in safe, malicious, poisoned order.",
            "",
            "```text",
            *[" ".join(str(value) for value in row) for row in metrics["confusion_matrix"]],
            "```",
            "",
            "## Data Integrity",
            "",
            f"- Unique wallets used: `{metrics['data']['usable_unique_wallets']}`",
            f"- Conflicting-label wallets dropped: `{metrics['data']['conflicting_wallets_dropped']}`",
            "- Scaling was fitted only on training data during model selection.",
            "- The test set was not oversampled and was evaluated once after selection.",
            "- A NOT MET result remains deployable only for assisted review, not autonomous blocking.",
            "- The concrete next step is collecting more independently verified malicious labels; unlabeled graph neighbors are never promoted to fraud labels automatically.",
            "",
        ]
    )
    return "\n".join(rows)


def write_performance_report(token: str, version: str | None = None) -> Path:
    """Rebuild a report from a stored model version's machine-readable metrics."""
    token = token.lower().strip()
    if version is None:
        active_path = Path("model_versions/active.json")
        if not active_path.exists():
            raise FileNotFoundError("No active model version registry exists")
        version = json.loads(active_path.read_text(encoding="utf-8")).get(token)
    if not version:
        raise FileNotFoundError(f"No active model version exists for {token.upper()}")
    metrics_path = Path("model_versions") / version / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Metrics not found for model version {version}")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    report_path = Path("docs/model_performance") / f"{token}_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_markdown_report(token, version, metrics), encoding="utf-8")
    return report_path


class ModelTrainer:
    def __init__(
        self,
        options: TrainingOptions,
        *,
        run_id: str | None = None,
        progress: Callable[[TrainingRun], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        options.validate()
        self.options = options
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.progress_callback = progress
        self.cancel_event = cancel_event or threading.Event()
        self.run = TrainingRun(
            run_id=self.run_id,
            status="queued",
            token=options.token,
            model=options.model,
        )

    def _update(self, progress: float, stage: str, message: str) -> None:
        self.run.progress = progress
        self.run.stage = stage
        self.run.message = message
        if self.progress_callback:
            self.progress_callback(self.run)

    def _tune_lightgbm(
        self,
        token: str,
        train: pd.DataFrame,
        cv: StratifiedKFold,
    ) -> tuple[Any, dict[str, Any]]:
        if not HAS_OPTUNA or not HAS_LGB:
            raise TrainingDataError(
                "Hyperparameter tuning requires optuna and lightgbm from requirements-ml.txt"
            )
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        y_train = train["label"]

        def objective(trial: Any) -> float:
            if self.cancel_event.is_set():
                raise optuna.TrialPruned("Training cancelled")
            model = LGBModel(
                n_estimators=trial.suggest_int("n_estimators", 150, 700, step=50),
                learning_rate=trial.suggest_float("learning_rate", 0.015, 0.12, log=True),
                num_leaves=trial.suggest_int("num_leaves", 12, 64),
                max_depth=trial.suggest_int("max_depth", 3, 16),
                min_child_samples=trial.suggest_int("min_child_samples", 5, 40),
                subsample=trial.suggest_float("subsample", 0.65, 1.0),
                colsample_bytree=trial.suggest_float("colsample_bytree", 0.65, 1.0),
                reg_alpha=trial.suggest_float("reg_alpha", 1e-5, 2.0, log=True),
                reg_lambda=trial.suggest_float("reg_lambda", 1e-5, 3.0, log=True),
                class_weight={0: 1.0, 1: trial.suggest_float("malicious_weight", 2.0, 12.0), 2: 4.0},
                random_state=self.options.random_seed,
                n_jobs=int(os.getenv("TRAIN_N_JOBS", "-1")),
                verbosity=-1,
            )
            pipeline = Pipeline([("scaler", StandardScaler()), ("model", model)])
            scores = cross_validate(
                pipeline,
                train[FEATURE_COLUMNS],
                y_train,
                cv=cv,
                scoring={
                    "macro_f1": "f1_macro",
                    "malicious_recall": make_scorer(
                        recall_score, labels=[1], average="macro", zero_division=0
                    ),
                    "poisoned_recall": make_scorer(
                        recall_score, labels=[2], average="macro", zero_division=0
                    ),
                },
                n_jobs=1,
            )
            macro = float(np.mean(scores["test_macro_f1"]))
            recall_floor = min(
                float(np.mean(scores["test_malicious_recall"])),
                float(np.mean(scores["test_poisoned_recall"])),
            )
            return macro * 0.75 + recall_floor * 0.25

        study = optuna.create_study(
            direction="maximize", sampler=optuna.samplers.TPESampler(seed=self.options.random_seed)
        )
        study.optimize(objective, n_trials=self.options.tuning_trials, show_progress_bar=False)
        params = dict(study.best_params)
        malicious_weight = params.pop("malicious_weight")
        model = LGBModel(
            **params,
            class_weight={0: 1.0, 1: malicious_weight, 2: 4.0},
            random_state=self.options.random_seed,
            n_jobs=int(os.getenv("TRAIN_N_JOBS", "-1")),
            verbosity=-1,
        )
        return model, {
            "engine": "optuna_tpe_lightgbm",
            "completed_trials": len(study.trials),
            "best_objective": float(study.best_value),
            "best_params": study.best_params,
            "token": token.upper(),
        }

    def train_token(self, token: str, ordinal: int, total: int) -> tuple[str, dict[str, Any]]:
        base = (ordinal - 1) / total
        span = 1 / total
        self._update(base + span * 0.05, "loading", f"Loading and validating {token.upper()} labels")
        data, data_info = load_training_data(token)
        splits = _split_data(data, self.options.random_seed)
        train = splits["train"]
        validation = splits["validation"]
        test = splits["test"]

        scaler = StandardScaler()
        x_train = scaler.fit_transform(train[FEATURE_COLUMNS])
        x_validation = scaler.transform(validation[FEATURE_COLUMNS])
        y_train = train["label"]
        y_validation = validation["label"]
        candidates = _models(self.options)

        smallest = int(y_train.value_counts().min())
        folds = min(self.options.cv_folds, smallest)
        cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=self.options.random_seed)
        tuning: dict[str, Any] = {"completed_trials": 0}
        if self.options.tuning_trials:
            self._update(
                base + span * 0.12,
                "hyperparameter_tuning",
                f"Running {self.options.tuning_trials} Optuna trials for {token.upper()}",
            )
            tuned_model, tuning = self._tune_lightgbm(token, train, cv)
            candidates["lgb_optuna"] = tuned_model
        candidate_metrics: dict[str, Any] = {}
        selected_name = ""
        selected_model: Any = None
        selected_score = -math.inf
        for index, (name, model) in enumerate(candidates.items(), start=1):
            if self.cancel_event.is_set():
                raise InterruptedError("Training cancelled")
            self._update(
                base + span * (0.15 + 0.45 * index / max(len(candidates), 1)),
                "cross_validation",
                f"Cross-validating {name.upper()} for {token.upper()}",
            )
            cv_pipeline = Pipeline([("scaler", StandardScaler()), ("model", clone(model))])
            scoring = {
                "macro_f1": "f1_macro",
                "malicious_recall": make_scorer(recall_score, labels=[1], average="macro", zero_division=0),
                "poisoned_recall": make_scorer(recall_score, labels=[2], average="macro", zero_division=0),
            }
            cv_results = cross_validate(
                cv_pipeline,
                train[FEATURE_COLUMNS],
                y_train,
                cv=cv,
                scoring=scoring,
                n_jobs=1,
            )
            cv_scores = cv_results["test_macro_f1"]
            model.fit(x_train, y_train)
            validation_predictions = model.predict(x_validation)
            validation_f1 = float(f1_score(y_validation, validation_predictions, average="macro"))
            validation_malicious_recall = float(
                recall_score(
                    y_validation,
                    validation_predictions,
                    labels=[1],
                    average="macro",
                    zero_division=0,
                )
            )
            validation_poisoned_recall = float(
                recall_score(
                    y_validation,
                    validation_predictions,
                    labels=[2],
                    average="macro",
                    zero_division=0,
                )
            )
            candidate_metrics[name] = {
                "cv_macro_f1_mean": float(np.mean(cv_scores)),
                "cv_macro_f1_std": float(np.std(cv_scores)),
                "cv_malicious_recall": float(np.mean(cv_results["test_malicious_recall"])),
                "cv_poisoned_recall": float(np.mean(cv_results["test_poisoned_recall"])),
                "validation_macro_f1": validation_f1,
                "validation_malicious_recall": validation_malicious_recall,
                "validation_poisoned_recall": validation_poisoned_recall,
            }
            recall_floor = min(
                candidate_metrics[name]["cv_malicious_recall"],
                candidate_metrics[name]["cv_poisoned_recall"],
                validation_malicious_recall,
                validation_poisoned_recall,
            )
            selection_score = float(np.mean(cv_scores)) * 0.55 + validation_f1 * 0.25 + recall_floor * 0.20
            if selection_score > selected_score:
                selected_score = selection_score
                selected_name = name
                selected_model = model

        self._update(base + span * 0.7, "final_fit", f"Fitting selected {selected_name.upper()} model")
        train_validation = pd.concat([train, validation], ignore_index=True)
        final_scaler = StandardScaler()
        x_train_validation = final_scaler.fit_transform(train_validation[FEATURE_COLUMNS])
        selected_model.fit(x_train_validation, train_validation["label"])
        x_test = final_scaler.transform(test[FEATURE_COLUMNS])
        y_test = test["label"]
        predictions = selected_model.predict(x_test)
        labels = [0, 1, 2]
        report = classification_report(
            y_test,
            predictions,
            labels=labels,
            target_names=[CLASS_NAMES[value] for value in labels],
            output_dict=True,
            zero_division=0,
        )
        matrix = confusion_matrix(y_test, predictions, labels=labels).tolist()
        version = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{self.run_id}-{token}"
        metrics = {
            "token": token.upper(),
            "version": version,
            "selected_model": selected_name,
            "test_macro_f1": float(f1_score(y_test, predictions, average="macro")),
            "test_accuracy": float(accuracy_score(y_test, predictions)),
            "malicious_recall": float(
                recall_score(y_test, predictions, labels=[1], average="macro", zero_division=0)
            ),
            "poisoned_recall": float(
                recall_score(y_test, predictions, labels=[2], average="macro", zero_division=0)
            ),
            "cv_macro_f1_mean": candidate_metrics[selected_name]["cv_macro_f1_mean"],
            "cv_macro_f1_std": candidate_metrics[selected_name]["cv_macro_f1_std"],
            "candidate_metrics": candidate_metrics,
            "classification_report": report,
            "confusion_matrix": matrix,
            "roc_auc_ovr": _safe_roc_auc(selected_model, x_test, y_test),
            "splits": {
                name: {"rows": int(len(frame)), "distribution": _distribution(frame)}
                for name, frame in splits.items()
            },
            "data": data_info,
            "feature_columns": FEATURE_COLUMNS,
            "generated_at": utc_now(),
            "tuning": tuning,
        }

        self._update(base + span * 0.85, "saving", f"Saving version {version}")
        version_dir = Path("model_versions") / version
        version_dir.mkdir(parents=True, exist_ok=False)
        with (version_dir / f"{token}_model.pkl").open("wb") as handle:
            pickle.dump(selected_model, handle)
        with (version_dir / f"{token}_scaler.pkl").open("wb") as handle:
            pickle.dump(final_scaler, handle)
        with (version_dir / f"{token}_features.pkl").open("wb") as handle:
            pickle.dump(FEATURE_COLUMNS, handle)
        (version_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        (version_dir / "manifest.json").write_text(
            json.dumps({"version": version, "token": token, "run_id": self.run_id, "active": True}, indent=2),
            encoding="utf-8",
        )

        model_dir = Path("models")
        model_dir.mkdir(exist_ok=True)
        for suffix in ("model.pkl", "scaler.pkl", "features.pkl"):
            source = version_dir / f"{token}_{suffix}"
            temporary = model_dir / f".{token}_{suffix}.tmp"
            shutil.copy2(source, temporary)
            temporary.replace(model_dir / f"{token}_{suffix}")
        active_versions = Path("model_versions/active.json")
        active = json.loads(active_versions.read_text(encoding="utf-8")) if active_versions.exists() else {}
        active[token] = version
        active_versions.write_text(json.dumps(active, indent=2), encoding="utf-8")

        write_performance_report(token, version)
        return version, metrics

    def execute(self) -> TrainingRun:
        tokens = list(TRAINABLE_TOKENS) if self.options.token == "all" else [self.options.token]
        self.run.status = "running"
        self._update(0.01, "starting", "Training started")
        failures: dict[str, str] = {}
        try:
            for ordinal, token in enumerate(tokens, start=1):
                try:
                    version, metrics = self.train_token(token, ordinal, len(tokens))
                    self.run.versions[token] = version
                    self.run.metrics[token] = {
                        "test_macro_f1": metrics["test_macro_f1"],
                        "test_accuracy": metrics["test_accuracy"],
                        "malicious_recall": metrics["malicious_recall"],
                        "poisoned_recall": metrics["poisoned_recall"],
                        "cv_macro_f1_mean": metrics["cv_macro_f1_mean"],
                        "cv_macro_f1_std": metrics["cv_macro_f1_std"],
                    }
                except TrainingDataError as exc:
                    failures[token] = str(exc)
                    if len(tokens) == 1:
                        raise
            if self.cancel_event.is_set():
                raise InterruptedError("Training cancelled")
            self.run.status = "partial" if failures else "success"
            self.run.message = (
                f"Trained {len(self.run.versions)} token model(s); {len(failures)} skipped for insufficient labels"
                if failures
                else f"Trained {len(self.run.versions)} token model(s) successfully"
            )
            if failures:
                self.run.metrics["skipped"] = failures
        except InterruptedError as exc:
            self.run.status = "cancelled"
            self.run.message = str(exc)
        except Exception as exc:
            self.run.status = "failed"
            self.run.message = str(exc)
        self.run.progress = 1.0
        self.run.stage = "finished"
        self.run.finished_at = utc_now()
        if self.progress_callback:
            self.progress_callback(self.run)
        return self.run


def rollback_model(token: str, version: str) -> dict[str, str]:
    token = token.lower().strip()
    if token not in TRAINABLE_TOKENS:
        raise ValueError(f"Unsupported token: {token}")
    version_dir = Path("model_versions") / version
    manifest_path = version_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Model version not found: {version}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("token") != token:
        raise ValueError(f"Version {version} belongs to {manifest.get('token')}, not {token}")
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    for suffix in ("model.pkl", "scaler.pkl", "features.pkl"):
        source = version_dir / f"{token}_{suffix}"
        if not source.exists():
            raise FileNotFoundError(f"Version artifact is incomplete: {source.name}")
        temporary = model_dir / f".{token}_{suffix}.tmp"
        shutil.copy2(source, temporary)
        temporary.replace(model_dir / f"{token}_{suffix}")
    active_path = Path("model_versions/active.json")
    active = json.loads(active_path.read_text(encoding="utf-8")) if active_path.exists() else {}
    active[token] = version
    active_path.write_text(json.dumps(active, indent=2), encoding="utf-8")
    return {"token": token, "version": version, "status": "active"}


def list_model_versions() -> dict[str, Any]:
    root = Path("model_versions")
    active_path = root / "active.json"
    active = json.loads(active_path.read_text(encoding="utf-8")) if active_path.exists() else {}
    versions: list[dict[str, Any]] = []
    if root.exists():
        for manifest_path in root.glob("*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                metrics_path = manifest_path.parent / "metrics.json"
                metrics = (
                    json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
                )
                token = str(manifest.get("token", ""))
                versions.append(
                    {
                        **manifest,
                        "active": active.get(token) == manifest.get("version"),
                        "metrics": {
                            key: metrics.get(key)
                            for key in (
                                "test_macro_f1",
                                "test_accuracy",
                                "malicious_recall",
                                "poisoned_recall",
                                "cv_macro_f1_mean",
                                "cv_macro_f1_std",
                            )
                        },
                    }
                )
            except (OSError, ValueError, json.JSONDecodeError):
                continue
    versions.sort(key=lambda item: str(item.get("version", "")), reverse=True)
    return {"active": active, "versions": versions}
