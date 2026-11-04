from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, average_precision_score, balanced_accuracy_score, f1_score, roc_auc_score


class TriageError(ValueError):
    pass


def risk_coverage_curve(errors: np.ndarray, confidence: np.ndarray) -> tuple[pd.DataFrame, float]:
    if len(errors) != len(confidence) or len(errors) == 0:
        raise TriageError("Risk-coverage inputs must have equal nonzero lengths")
    error_values = np.asarray(errors, dtype=float)
    confidence_values = np.asarray(confidence, dtype=float)
    if not np.all(np.isfinite(error_values)) or not np.all(np.isfinite(confidence_values)):
        raise TriageError("Risk-coverage inputs must be finite")
    if np.any((error_values < 0) | (error_values > 1)):
        raise TriageError("Risk values must lie in [0, 1]")
    order = np.argsort(-confidence_values, kind="stable")
    cumulative_risk = np.cumsum(error_values[order]) / np.arange(1, len(order) + 1)
    coverage = np.arange(1, len(order) + 1) / len(order)
    curve = pd.DataFrame({"coverage": coverage, "risk": cumulative_risk})
    return curve, float(np.mean(cumulative_risk))


def evaluate_triage(
    probabilities: np.ndarray,
    prediction_sets: np.ndarray,
    evidence_margin: np.ndarray,
    osr_scores: np.ndarray,
    osr_rejected: np.ndarray,
    y_true: np.ndarray,
    class_ids: np.ndarray,
    id_to_label: dict[int, str],
    minimum_margin: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], pd.DataFrame]:
    y_true = np.asarray(y_true, dtype=int)
    class_ids = np.asarray(class_ids, dtype=int)
    evidence_margin = np.asarray(evidence_margin, dtype=float)
    osr_scores = np.asarray(osr_scores, dtype=float)
    osr_rejected = np.asarray(osr_rejected, dtype=bool)
    prediction_sets = np.asarray(prediction_sets, dtype=bool)
    probabilities = np.asarray(probabilities, dtype=float)
    n = len(y_true)
    if probabilities.ndim != 2 or probabilities.shape[0] != n or prediction_sets.shape != probabilities.shape:
        raise TriageError("Prediction arrays do not match the number of test labels")
    if class_ids.ndim != 1 or len(class_ids) != probabilities.shape[1] or len(np.unique(class_ids)) != len(class_ids):
        raise TriageError("class_ids must be unique and match the probability columns")
    if any(len(x) != n for x in (evidence_margin, osr_scores, osr_rejected)):
        raise TriageError("OSR and confidence vectors do not match test labels")
    if n == 0:
        raise TriageError("Triage evaluation requires at least one test observation")
    if (not np.all(np.isfinite(probabilities)) or np.any(probabilities < 0)
            or np.any(probabilities > 1) or not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-5)):
        raise TriageError("Probabilities must be finite, lie in [0, 1], and sum to one")
    if not np.all(np.isfinite(evidence_margin)) or np.any((evidence_margin < 0) | (evidence_margin > 1)):
        raise TriageError("Evidence margins must be finite and lie in [0, 1]")
    if not np.all(np.isfinite(osr_scores)) or np.any((osr_scores < 0) | (osr_scores > 1)):
        raise TriageError("OSR scores must be finite and lie in [0, 1]")
    if not 0 <= minimum_margin <= 1:
        raise TriageError("minimum_margin must be in [0, 1]")
    top_column = np.argmax(probabilities, axis=1)
    predicted_known = class_ids[top_column]
    predicted_final = np.where(osr_rejected, -1, predicted_known)
    set_size = prediction_sets.sum(axis=1)
    singleton_column = np.argmax(prediction_sets, axis=1)
    singleton_class = class_ids[singleton_column]
    singleton_agrees_with_top1 = (set_size == 1) & (singleton_class == predicted_known)
    automated = (
        (set_size == 1)
        & singleton_agrees_with_top1
        & (~osr_rejected)
        & (evidence_margin >= minimum_margin)
    )
    escalated = ~automated

    route_reason = np.full(n, "automated", dtype=object)
    route_reason[evidence_margin < minimum_margin] = "evidence_margin_below_threshold"
    route_reason[(set_size > 1)] = "multiple_conformal_labels"
    route_reason[(set_size == 0)] = "empty_conformal_set"
    route_reason[(set_size == 1) & (~singleton_agrees_with_top1)] = "singleton_disagrees_with_top1"
    route_reason[osr_rejected] = "osr_rejected"

    conformal_set_labels = [
        "{" + ", ".join(id_to_label.get(int(class_ids[col]), str(int(class_ids[col]))) for col in np.where(row)[0]) + "}"
        for row in prediction_sets
    ]
    records = pd.DataFrame({
        "true_class_id": y_true.astype(int),
        "true_class": [id_to_label.get(int(v), "Unknown_held_out") for v in y_true],
        # Preserve the classifier's closed-set decision before the OSR layer
        # replaces rejected predictions with the -1 review sentinel.
        "closed_set_predicted_class_id": predicted_known.astype(int),
        "closed_set_predicted_class": [id_to_label.get(int(v), "Unknown_held_out") for v in predicted_known],
        "predicted_class_id": predicted_final.astype(int),
        "predicted_class": [id_to_label.get(int(v), "Unknown_held_out") for v in predicted_final],
        "conformal_prediction_set": conformal_set_labels,
        "conformal_set_size": set_size.astype(int),
        "evidence_margin": evidence_margin.astype(float),
        "osr_score": osr_scores.astype(float),
        "closed_set_max_probability_unknown_score": (1.0 - np.max(probabilities, axis=1)).astype(float),
        "osr_rejected": osr_rejected.astype(bool),
        "singleton_set_agrees_with_top1": singleton_agrees_with_top1,
        "route_reason": route_reason,
        "route": np.where(automated, "automated", "analyst_review"),
    })

    class_rows = []
    for class_id in sorted(np.unique(y_true).tolist()):
        mask = y_true == class_id
        accepted = mask & automated
        if class_id >= 0:
            col = int(np.where(class_ids == class_id)[0][0])
            cp_coverage = float(prediction_sets[mask, col].mean())
        else:
            cp_coverage = float("nan")
        class_rows.append({
            "class_id": int(class_id),
            "class": id_to_label.get(int(class_id), "Unknown_held_out"),
            "support": int(mask.sum()),
            "closed_set_top1_recall": float(np.mean(predicted_known[mask] == class_id)) if class_id >= 0 else float("nan"),
            "final_prediction_recall_after_osr": float(np.mean(predicted_final[mask] == class_id)),
            "empirical_conformal_coverage": cp_coverage,
            "osr_rejection_rate": float(osr_rejected[mask].mean()),
            "analyst_escalation_rate": float(escalated[mask].mean()),
            "autonomous_acceptance_rate": float(automated[mask].mean()),
            "automated_subset_accuracy": float(np.mean(predicted_final[accepted] == y_true[accepted])) if accepted.any() else float("nan"),
        })
    per_class = pd.DataFrame(class_rows)

    automated_accuracy = float(np.mean(predicted_final[automated] == y_true[automated])) if automated.any() else float("nan")
    benign = y_true == 0
    benign_false_alarm = float(np.mean(predicted_final[benign] != 0)) if benign.any() else float("nan")
    unknown = y_true == -1
    unknown_osr_tpr = float(osr_rejected[unknown].mean()) if unknown.any() else float("nan")
    unknown_escalation = float(escalated[unknown].mean()) if unknown.any() else float("nan")
    unknown_auto_accept = float(automated[unknown].mean()) if unknown.any() else float("nan")
    known = y_true >= 0
    known_osr_fpr = float(osr_rejected[known].mean()) if known.any() else float("nan")

    errors = predicted_final != y_true
    curve, aurc = risk_coverage_curve(errors, evidence_margin)
    metrics: dict[str, float] = {
        "test_rows": float(n),
        "automated_coverage_rate": float(automated.mean()),
        "automated_rows": float(automated.sum()),
        "automated_subset_accuracy": automated_accuracy,
        "singleton_set_top1_disagreement_rate": float(
            np.mean((set_size == 1) & (~singleton_agrees_with_top1))
        ),
        "singleton_set_top1_disagreement_rows": float(
            np.sum((set_size == 1) & (~singleton_agrees_with_top1))
        ),
        "analyst_escalation_rate": float(escalated.mean()),
        "benign_false_alarm_rate_all_predictions": benign_false_alarm,
        "known_class_osr_false_rejection_rate": known_osr_fpr,
        "unknown_osr_detection_rate": unknown_osr_tpr,
        "unknown_analyst_escalation_rate": unknown_escalation,
        "unknown_autonomous_acceptance_rate": unknown_auto_accept,
        "evidence_margin_aurc_all_test_flows": aurc,
    }
    if known.any():
        metrics["known_test_closed_set_accuracy"] = float(accuracy_score(y_true[known], predicted_known[known]))
        metrics["known_test_closed_set_macro_f1"] = float(f1_score(y_true[known], predicted_known[known], average="macro", zero_division=0))
        metrics["known_test_closed_set_balanced_accuracy"] = float(balanced_accuracy_score(y_true[known], predicted_known[known]))
        metrics["known_test_final_prediction_accuracy_after_osr"] = float(accuracy_score(y_true[known], predicted_final[known]))
    else:
        metrics["known_test_closed_set_accuracy"] = float("nan")
        metrics["known_test_closed_set_macro_f1"] = float("nan")
        metrics["known_test_closed_set_balanced_accuracy"] = float("nan")
        metrics["known_test_final_prediction_accuracy_after_osr"] = float("nan")
    if unknown.any() and known.any():
        y_binary = unknown.astype(int)
        max_prob_unknown_score = 1.0 - np.max(probabilities, axis=1)
        metrics["unknown_detection_auroc_evt"] = float(roc_auc_score(y_binary, osr_scores))
        metrics["unknown_detection_aupr_evt"] = float(average_precision_score(y_binary, osr_scores))
        metrics["unknown_detection_auroc_max_probability_baseline"] = float(roc_auc_score(y_binary, max_prob_unknown_score))
        metrics["unknown_detection_aupr_max_probability_baseline"] = float(average_precision_score(y_binary, max_prob_unknown_score))
        metrics["unknown_test_prevalence"] = float(unknown.mean())
    else:
        metrics["unknown_detection_auroc_evt"] = float("nan")
        metrics["unknown_detection_aupr_evt"] = float("nan")
        metrics["unknown_detection_auroc_max_probability_baseline"] = float("nan")
        metrics["unknown_detection_aupr_max_probability_baseline"] = float("nan")
        metrics["unknown_test_prevalence"] = float(unknown.mean())
    return records, per_class, metrics, curve
