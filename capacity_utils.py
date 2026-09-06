# =============================================================================
# capacity_utils.py
# Small, independent helper functions: parsing cycle numbers, ordinal
# names, title formatting, charge/discharge detection, colors.
# =============================================================================

import re

import numpy as np
import matplotlib.pyplot as plt

from config import COL_CHARGE_CAPACITY, COL_DISCHARGE_CAPACITY, COL_CURRENT, CAPACITY_CHANGE_TOLERANCE_AH


def parse_cycle_numbers(cycle_text):
    """Parse '1, 20, 25' or '1 20 25' into a de-duplicated list of ints. Used in single-file mode."""
    parts = re.split(r"[,\s]+", cycle_text.strip())
    numbers = [int(p) for p in parts if p != ""]
    if len(numbers) == 0:
        raise ValueError("No cycle numbers entered.")
    return list(dict.fromkeys(numbers))


def parse_single_cycle_number(cycle_text):
    """Parse exactly one cycle number. Used in multi-file mode."""
    text = cycle_text.strip()
    if text == "":
        raise ValueError("Enter one cycle number.")
    parts = re.split(r"[,\s]+", text)
    parts = [p for p in parts if p != ""]
    if len(parts) != 1:
        raise ValueError("Enter exactly ONE cycle number when comparing multiple files.")
    return int(parts[0])


def ordinal_cycle_name(number):
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix} cycle"


def prepare_title(text):
    """Wraps things like MoWS$_2$ into $MoWS_2$ so newer Matplotlib renders it safely."""
    return re.sub(
        r'\S*\$[^\s$]+\$\S*',
        lambda m: "$" + m.group(0).replace("$", "") + "$",
        text,
    )


def identify_segment_type(segment):
    """Look at actual capacity change (not step-number assumptions) to decide charge vs discharge."""
    charge_values = segment[COL_CHARGE_CAPACITY].dropna()
    discharge_values = segment[COL_DISCHARGE_CAPACITY].dropna()

    charge_change = (charge_values.max() - charge_values.min()) if len(charge_values) > 0 else 0.0
    discharge_change = (discharge_values.max() - discharge_values.min()) if len(discharge_values) > 0 else 0.0

    if discharge_change > charge_change and discharge_change > CAPACITY_CHANGE_TOLERANCE_AH:
        return "discharge"
    if charge_change > discharge_change and charge_change > CAPACITY_CHANGE_TOLERANCE_AH:
        return "charge"

    mean_current = segment[COL_CURRENT].mean()
    return "discharge" if mean_current < 0 else "charge"


def get_cycle_colors(n):
    """Same color-count logic as before, now reused for either 'per cycle' or 'per file' coloring."""
    if n <= 10:
        cmap = plt.get_cmap("tab10")
        return [cmap(i) for i in range(n)]
    if n <= 20:
        cmap = plt.get_cmap("tab20")
        return [cmap(i) for i in range(n)]
    cmap = plt.get_cmap("turbo")
    return cmap(np.linspace(0, 1, n))
