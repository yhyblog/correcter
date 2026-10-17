"""Represent only the native evaluator's undefined summary statistics as null.

No model, action, observed value, threshold, or finite metric is changed.
Unexpected nonfinite values remain errors rather than silently disappearing.
"""
import math


def native_summary_for_json(row):
    result = dict(row)
    reasons = {}
    no_valid = {
        "exceed_ratio_valid", "et_mean", "et_std", "et_max", "et_p95",
        "threshold_mean", "threshold_max",
    }
    for key, value in row.items():
        if not isinstance(value, float) or math.isfinite(value):
            continue
        if not math.isnan(value):
            raise ValueError(f"Unexpected infinite native summary field: {key}")
        if key in no_valid and row["num_et_valid"] == 0:
            reason = "no_finite_error_and_threshold_pairs"
        elif key == "recovery_rate_after_meltdown" and row["meltdown_count"] == 0:
            reason = "no_meltdown_events"
        elif key == "recovery_steps_mean" and row["recovery_count"] == 0:
            reason = "no_observed_recoveries"
        else:
            raise ValueError(f"Unexpected NaN native summary field: {key}")
        result[key] = None
        reasons[key] = reason
    return result, reasons
