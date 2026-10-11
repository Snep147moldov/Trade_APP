"""Experimental probability filter: regularized logistic regression, pure numpy.

The scaler and coefficients are fitted on training data only. Calibration uses
a later, disjoint window. This module never enables live trading or modifies
strategy weights. Probabilities require forward validation before deployment.
"""

import numpy as np

FEATURES = ("score_strength", "rsi_alignment", "band_alignment", "trend_alignment",
            "macd_alignment", "adx", "efficiency", "cost_ratio")


def entry_features(snap: dict, score: float, cost_ratio: float) -> list[float]:
    side = 1 if score > 0 else -1
    atr = max(snap["atr14"] or 0, 1e-12)
    return [abs(score), side * ((snap["rsi14"] if snap["rsi14"] is not None else 50) - 50) / 50,
            side * float(np.clip(2 * (0.5 - (snap["pct_b"] if snap["pct_b"] is not None else 0.5)), -1, 1)),
            side * float(np.tanh((snap["ema20"] - snap["ema50"]) / atr)),
            side * float(np.tanh(2 * (snap["macd_hist"] or 0) / atr)),
            (snap["adx14"] or 0) / 100, abs(snap["er_signed"]), min(cost_ratio, 2.0)]


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -35, 35)))


def fit(x, y, l2: float = 10.0) -> dict:
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 2 or len(y) != len(x) or len(y) < 30 or not np.isfinite(x).all():
        raise ValueError("insufficient or invalid training observations")
    if not ((y == 0) | (y == 1)).all() or y.min() == y.max():
        raise ValueError("training needs both winning and losing labels")
    center, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.where(scale > 1e-9, scale, 1.0)
    design = np.column_stack((np.ones(len(x)), (x - center) / scale))
    coef = np.zeros(design.shape[1])
    coef[0] = np.log(y.mean() / (1 - y.mean()))
    penalty = np.eye(len(coef)) * l2
    penalty[0, 0] = 0
    for _ in range(60):
        probs = sigmoid(design @ coef)
        gradient = design.T @ (probs - y) + penalty @ coef
        hessian = design.T @ ((probs * (1 - probs))[:, None] * design) + penalty
        step = np.linalg.solve(hessian + np.eye(len(coef)) * 1e-8, gradient)
        coef -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return {"center": center.tolist(), "scale": scale.tolist(), "coef": coef.tolist(),
            "features": list(FEATURES) if x.shape[1] == len(FEATURES) else ["logit"], "l2": l2}


def predict(model: dict, x) -> np.ndarray:
    x = np.atleast_2d(np.asarray(x, dtype=float))
    z = (x - np.asarray(model["center"])) / np.asarray(model["scale"])
    coef = np.asarray(model["coef"])
    return sigmoid(coef[0] + z @ coef[1:])


def calibrated_predict(model: dict, calibration: dict, x) -> np.ndarray:
    probs = np.clip(predict(model, x), 1e-6, 1 - 1e-6)
    logits = np.log(probs / (1 - probs))[:, None]
    return predict(calibration, logits)
