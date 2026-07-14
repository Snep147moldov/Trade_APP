"""Deterministic technical indicators, pure numpy.

All functions take/return float64 arrays aligned to the input series,
NaN-padded where the indicator has no value yet. Formulas follow the
standard definitions (Wilder smoothing for RSI/ATR/ADX).
"""

import numpy as np


def sma(values: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=np.float64)
    if len(values) < period:
        return out
    csum = np.cumsum(np.insert(values, 0, 0.0))
    out[period - 1:] = (csum[period:] - csum[:-period]) / period
    return out


def ema(values: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=np.float64)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    out[period - 1] = values[:period].mean()  # seed with SMA
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def _wilder_smooth(values: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothing (RMA): seed with SMA, then s = (s*(n-1) + x) / n."""
    out = np.full_like(values, np.nan, dtype=np.float64)
    if len(values) < period:
        return out
    out[period - 1] = values[:period].mean()
    for i in range(period, len(values)):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return out


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=np.float64)
    if len(close) < period + 1:
        return out
    delta = np.diff(close)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    avg_gain = _wilder_smooth(gains, period)
    avg_loss = _wilder_smooth(losses, period)
    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.inf), where=avg_loss != 0)
    out[1:] = 100.0 - 100.0 / (1.0 + rs)
    out[1:][np.isnan(avg_gain)] = np.nan
    return out


def macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal_p: int = 9):
    line = ema(close, fast) - ema(close, slow)
    valid = ~np.isnan(line)
    signal = np.full_like(line, np.nan)
    if valid.sum() >= signal_p:
        signal[valid] = ema(line[valid], signal_p)
    hist = line - signal
    return line, signal, hist


def bollinger(close: np.ndarray, period: int = 20, num_std: float = 2.0):
    mid = sma(close, period)
    std = np.full_like(close, np.nan, dtype=np.float64)
    for i in range(period - 1, len(close)):
        std[i] = close[i - period + 1: i + 1].std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    # %B: 0 at lower band, 1 at upper band, 0.5 at the middle
    width = upper - lower
    pct_b = np.divide(close - lower, width, out=np.full_like(close, 0.5), where=width != 0)
    return mid, upper, lower, pct_b


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    return np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    return _wilder_smooth(true_range(high, low, close), period)


def stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               k_period: int = 14, smooth_k: int = 3, d_period: int = 3):
    n = len(close)
    raw_k = np.full(n, np.nan, dtype=np.float64)
    for i in range(k_period - 1, n):
        hh = high[i - k_period + 1: i + 1].max()
        ll = low[i - k_period + 1: i + 1].min()
        raw_k[i] = 50.0 if hh == ll else (close[i] - ll) / (hh - ll) * 100.0
    k = sma(np.nan_to_num(raw_k, nan=50.0), smooth_k)
    k[np.isnan(raw_k)] = np.nan
    d = sma(np.nan_to_num(k, nan=50.0), d_period)
    d[np.isnan(k)] = np.nan
    return k, d


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14):
    n = len(close)
    up = high[1:] - high[:-1]
    down = low[:-1] - low[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(high, low, close)[1:]

    atr_s = _wilder_smooth(tr, period)
    plus_s = _wilder_smooth(plus_dm, period)
    minus_s = _wilder_smooth(minus_dm, period)

    plus_di = np.full(n, np.nan)
    minus_di = np.full(n, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di[1:] = 100.0 * plus_s / atr_s
        minus_di[1:] = 100.0 * minus_s / atr_s
        di_sum = plus_di + minus_di
        dx = np.where(di_sum != 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)

    adx_out = np.full(n, np.nan)
    dx_valid = dx[~np.isnan(dx)]
    if len(dx_valid) >= period:
        smoothed = _wilder_smooth(dx_valid, period)
        adx_out[np.where(~np.isnan(dx))[0]] = smoothed
    return adx_out, plus_di, minus_di


def roc(close: np.ndarray, period: int = 10) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=np.float64)
    out[period:] = (close[period:] - close[:-period]) / close[:-period] * 100.0
    return out


def efficiency_ratio(close: np.ndarray, period: int = 10) -> float:
    """Kaufman Efficiency Ratio (Kaufman, 'Smarter Trading', 1995):
    net change over the path length, in [0, 1]. 1 = perfectly directional."""
    if len(close) < period + 1:
        return 0.0
    change = abs(close[-1] - close[-1 - period])
    path = np.abs(np.diff(close[-1 - period:])).sum()
    return float(change / path) if path > 0 else 0.0


def vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray,
         volume: np.ndarray, window: int = 48) -> np.ndarray:
    """Rolling VWAP over `window` bars (session-agnostic markets like forex
    have no daily reset, so a rolling anchor is the standard substitute)."""
    tp = (high + low + close) / 3.0
    pv = tp * volume
    out = np.full_like(close, np.nan, dtype=np.float64)
    cpv = np.cumsum(np.insert(pv, 0, 0.0))
    cv = np.cumsum(np.insert(volume.astype(np.float64), 0, 0.0))
    for i in range(window - 1, len(close)):
        vol = cv[i + 1] - cv[i + 1 - window]
        out[i] = (cpv[i + 1] - cpv[i + 1 - window]) / vol if vol > 0 else np.nan
    return out


def ichimoku(high: np.ndarray, low: np.ndarray,
             tenkan_p: int = 9, kijun_p: int = 26, senkou_b_p: int = 52):
    """Returns (tenkan, kijun, senkou_a, senkou_b) — senkou spans already
    shifted forward by kijun_p bars (NaN-padded), standard Ichimoku plotting."""
    n = len(high)

    def midline(period: int) -> np.ndarray:
        out = np.full(n, np.nan, dtype=np.float64)
        for i in range(period - 1, n):
            out[i] = (high[i - period + 1:i + 1].max()
                      + low[i - period + 1:i + 1].min()) / 2.0
        return out

    tenkan = midline(tenkan_p)
    kijun = midline(kijun_p)
    raw_a = (tenkan + kijun) / 2.0
    raw_b = midline(senkou_b_p)
    senkou_a = np.full(n, np.nan)
    senkou_b = np.full(n, np.nan)
    senkou_a[kijun_p:] = raw_a[:-kijun_p]
    senkou_b[kijun_p:] = raw_b[:-kijun_p]
    return tenkan, kijun, senkou_a, senkou_b


def hurst_exponent(close: np.ndarray, window: int = 100) -> float:
    """Rescaled-range (R/S) Hurst exponent on log returns (Hurst 1951;
    Lo 1991). H > 0.5 persistent/trending, H < 0.5 mean-reverting,
    H ~ 0.5 random walk. Returns 0.5 when there is not enough data."""
    if len(close) < window + 1:
        return 0.5
    rets = np.diff(np.log(close[-window - 1:]))
    lags = [10, 20, 50, window]
    points: list[tuple[float, float]] = []
    for lag in lags:
        chunks = len(rets) // lag
        if chunks == 0:
            continue
        rs_vals = []
        for i in range(chunks):
            chunk = rets[i * lag:(i + 1) * lag]
            std = chunk.std(ddof=0)
            if std == 0:
                continue
            dev = np.cumsum(chunk - chunk.mean())
            rs_vals.append((dev.max() - dev.min()) / std)
        if rs_vals:
            points.append((float(np.log(lag)), float(np.log(np.mean(rs_vals)))))
    if len(points) < 2:
        return 0.5
    xs = np.array([p[0] for p in points])
    ys = np.array([p[1] for p in points])
    h = float(np.polyfit(xs, ys, 1)[0])
    return min(1.0, max(0.0, h))
