"""Calculs du dashboard sans dépendance à Tkinter ou MySQL."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from tap.core.models import SubscriptionRecord


class DashboardCache:
    """Cache TTL indépendant de l'interface graphique."""

    def __init__(self, ttl: float = 5):
        self.cache: dict[str, tuple[object, float]] = {}
        self.ttl = ttl
        self.hits = 0
        self.misses = 0

    def get(self, key: str, compute_func):
        cached = self.cache.get(key)
        if cached and time.time() - cached[1] < self.ttl:
            self.hits += 1
            return cached[0]
        self.misses += 1
        value = compute_func()
        self.cache[key] = (value, time.time())
        return value

    def invalidate(self) -> None:
        self.cache.clear()


@dataclass(frozen=True)
class DashboardMetrics:
    total_amount: float
    average_amount: float
    maximum_amount: float
    count: int
    currencies: tuple[str, ...]
    busiest_month: str
    busiest_month_count: int

    @property
    def has_multiple_currencies(self) -> bool:
        return len(self.currencies) > 1


def calculate_dashboard_metrics(records: Iterable[SubscriptionRecord]) -> DashboardMetrics:
    """Calcule les indicateurs du dashboard à partir de modèles typés."""
    records = list(records)
    amounts = []
    for record in records:
        try:
            amounts.append(float(str(record.amount).replace(",", ".")))
        except (TypeError, ValueError):
            continue

    currencies = tuple(sorted({record.currency.upper() for record in records if record.currency.strip()}))
    months = Counter(str(record.month) for record in records)
    busiest_month, busiest_count = months.most_common(1)[0] if months else ("—", 0)
    total = sum(amounts)
    return DashboardMetrics(
        total_amount=total,
        average_amount=total / len(amounts) if amounts else 0,
        maximum_amount=max(amounts) if amounts else 0,
        count=len(records),
        currencies=currencies,
        busiest_month=busiest_month,
        busiest_month_count=busiest_count,
    )
