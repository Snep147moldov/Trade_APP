"""Replay only AI vectors that were actually recorded before a decision."""

from bisect import bisect_right
from datetime import datetime, timezone
import json
import math


class AIHistory:
    def __init__(self, rows: list[dict]):
        self.rows = []
        for row in rows:
            dt = row['created_at']
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            vector = row.get('vector') or {}
            biases = row.get('pair_biases') or {}
            self.rows.append((dt.timestamp(), json.loads(vector) if isinstance(vector, str) else vector,
                              json.loads(biases) if isinstance(biases, str) else biases))
        self.rows.sort(key=lambda r: r[0])
        self.times = [r[0] for r in self.rows]

    def at(self, timestamp: float, instrument: str) -> tuple[float, float, bool]:
        i = bisect_right(self.times, timestamp) - 1
        if i < 0:
            return 0., 0., False
        ts, vector, biases = self.rows[i]
        base, quote = instrument.split('_')
        news = vector.get(base, 0.) - vector.get(quote, 0.)
        prediction = (biases.get(instrument) or {}).get('bias', 0.)
        if not math.isfinite(news) or not math.isfinite(prediction):
            raise ValueError('nonfinite historical AI vector')
        decay = 0.5 ** ((timestamp - ts) / (12 * 3600))
        return max(-1., min(1., news)) * decay, max(-1., min(1., prediction)) * decay, True
