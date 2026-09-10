# =============================================================================
# config.py
# All constants and cell-type definitions live here. Nothing to run —
# other files import from this one.
# =============================================================================

import numpy as np

# -----------------------------------------------------------------------------
# Column names expected in the Neware-style Excel sheets
# -----------------------------------------------------------------------------

COL_STEP = "Step_Index"
COL_CYCLE = "Cycle_Index"
COL_CURRENT = "Current(A)"
COL_VOLTAGE = "Voltage(V)"
COL_CHARGE_CAPACITY = "Charge_Capacity(Ah)"
COL_DISCHARGE_CAPACITY = "Discharge_Capacity(Ah)"

SPECIFIC_CHARGE_COLUMN = "Specific_Charge_Capacity(mAh/g)"
SPECIFIC_DISCHARGE_COLUMN = "Specific_Discharge_Capacity(mAh/g)"

REQUIRED_COLUMNS = [
    COL_STEP, COL_CYCLE, COL_CURRENT, COL_VOLTAGE,
    COL_CHARGE_CAPACITY, COL_DISCHARGE_CAPACITY,
]

# -----------------------------------------------------------------------------
# Plot defaults
# -----------------------------------------------------------------------------

FIGURE_WIDTH = 7.0
FIGURE_HEIGHT = 6.0
LINE_WIDTH = 2.0
AXIS_LINE_WIDTH = 1.5

CURRENT_ZERO_TOLERANCE = 1e-12
CAPACITY_CHANGE_TOLERANCE_AH = 1e-12

# If the local voltage derivative (dV) is essentially zero, dQ/dV is
# mathematically undefined at that point. That point becomes NaN
# rather than shifting to a different voltage.
DV_ZERO_TOLERANCE = 1e-12

DEFAULT_TITLE_FONT_SIZE = 15
DEFAULT_AXIS_LABEL_FONT_SIZE = 14
DEFAULT_TICK_FONT_SIZE = 12
DEFAULT_LEGEND_FONT_SIZE = 11

# -----------------------------------------------------------------------------
# Battery-type presets (controls the y-axis)
# -----------------------------------------------------------------------------

CELL_TYPES = {
    "Lithium-ion battery": {
        "y_label": r"Voltage (|V| vs. $Li/Li^{+}$)",
        "y_limits": (-0.25, 2.75),
        "y_ticks": np.arange(0.0, 2.51, 0.5),
    },
    "Sodium-ion battery": {
        "y_label": r"Voltage (|V| vs. $Na/Na^{+}$)",
        "y_limits": (-0.25, 2.75),
        "y_ticks": np.arange(0.0, 2.51, 0.5),
    },
    "Potassium-ion battery": {
        "y_label": r"Voltage (|V| vs. $K/K^{+}$)",
        "y_limits": (-0.25, 2.75),
        "y_ticks": np.arange(0.0, 2.51, 0.5),
    },
    "Lithium-sulfur battery": {
        "y_label": r"Voltage (|V| vs. $Li^{+}/Li^{0}$)",
        "y_limits": (1.65, 2.75),
        "y_ticks": np.arange(1.7, 2.71, 0.2),
    },
}
