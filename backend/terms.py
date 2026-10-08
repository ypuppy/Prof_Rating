"""NUS academic calendar helpers. Academic years start in August."""
from datetime import date
from typing import Optional


def current_academic_year(today: Optional[date] = None) -> int:
    """Start year of the current academic year: Oct 2026 -> 2026 (AY26/27), Mar 2026 -> 2025."""
    today = today or date.today()
    return today.year if today.month >= 8 else today.year - 1
