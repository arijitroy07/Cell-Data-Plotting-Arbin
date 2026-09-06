# =============================================================================
# excel_reader.py
# Everything related to opening a workbook, finding raw-data sheets,
# combining them, converting to specific capacity, and reading the
# statistics sheet for cycling-stability analysis.
# =============================================================================

import io
import re

import numpy as np
import pandas as pd

from config import (
    COL_STEP, COL_CYCLE, COL_CURRENT, COL_VOLTAGE,
    COL_CHARGE_CAPACITY, COL_DISCHARGE_CAPACITY,
    SPECIFIC_CHARGE_COLUMN, SPECIFIC_DISCHARGE_COLUMN,
    REQUIRED_COLUMNS, CURRENT_ZERO_TOLERANCE,
)

COULOMBIC_EFFICIENCY_COLUMN = "Coulombic_Efficiency(%)"


def normalize_sheet_name(sheet_name):
    return re.sub(r"[^a-z0-9]", "", str(sheet_name).lower())


def find_raw_data_sheets(sheet_names):
    normalized_names = [normalize_sheet_name(n) for n in sheet_names]

    info_index = None
    for i, name in enumerate(normalized_names):
        if name == "info":
            info_index = i
            break
    if info_index is None:
        raise ValueError('Could not find the "Info" sheet in this Excel file.')

    stop_index = None
    for i in range(info_index + 1, len(sheet_names)):
        name = normalized_names[i]
        if name.startswith("channelchart") or name.startswith("statistics"):
            stop_index = i
            break
    if stop_index is None:
        raise ValueError('Could not find "Channel_Chart" or "Statistics" after Info.')

    raw_data_sheets = sheet_names[info_index + 1: stop_index]
    if len(raw_data_sheets) == 0:
        raise ValueError("No raw battery-data sheets were found between Info and Channel_Chart/Statistics.")
    return raw_data_sheets


def load_and_process(file_bytes, active_mass_mg):
    """
    Read one workbook (as raw bytes), combine its raw-data sheets,
    convert Ah -> mAh/g, and remove resting rows.

    Returns: all_sheet_names, raw_data_sheets, battery_data, active_data
    """
    excel_file = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    all_sheet_names = excel_file.sheet_names
    raw_data_sheets = find_raw_data_sheets(all_sheet_names)

    data_frames = []
    for sheet_name in raw_data_sheets:
        sheet_data = pd.read_excel(excel_file, sheet_name=sheet_name, usecols="A:Q", engine="openpyxl")
        sheet_data.columns = [str(c).strip() for c in sheet_data.columns]

        missing = [c for c in REQUIRED_COLUMNS if c not in sheet_data.columns]
        if missing:
            raise ValueError(f"Sheet '{sheet_name}' is missing required columns: {missing}")

        sheet_data["_Source_Sheet"] = sheet_name
        data_frames.append(sheet_data)

    excel_file.close()

    battery_data = pd.concat(data_frames, ignore_index=True)
    battery_data["_Original_Row_Order"] = np.arange(len(battery_data))

    numeric_columns = [COL_STEP, COL_CYCLE, COL_CURRENT, COL_VOLTAGE, COL_CHARGE_CAPACITY, COL_DISCHARGE_CAPACITY]
    for col in numeric_columns:
        battery_data[col] = pd.to_numeric(battery_data[col], errors="coerce")

    battery_data = battery_data.dropna(subset=[COL_STEP, COL_CYCLE, COL_CURRENT, COL_VOLTAGE]).copy()

    battery_data[SPECIFIC_CHARGE_COLUMN] = battery_data[COL_CHARGE_CAPACITY] * 1_000_000 / active_mass_mg
    battery_data[SPECIFIC_DISCHARGE_COLUMN] = battery_data[COL_DISCHARGE_CAPACITY] * 1_000_000 / active_mass_mg

    step_is_not_rest = ~np.isclose(battery_data[COL_STEP], 1.0)
    current_is_not_zero = ~np.isclose(battery_data[COL_CURRENT], 0.0, atol=CURRENT_ZERO_TOLERANCE)
    active_data = battery_data[step_is_not_rest & current_is_not_zero].copy()

    return all_sheet_names, raw_data_sheets, battery_data, active_data


def load_statistics_and_process(file_bytes, active_mass_mg, battery_type_name):
    """
    Read ONLY the last sheet (Statistics) from one workbook, convert
    charge/discharge capacities to specific capacities, and calculate
    coulombic efficiency.

    Returns: all_sheet_names, statistics_sheet_name, statistics_data
    """
    excel_file = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    all_sheet_names = excel_file.sheet_names

    if len(all_sheet_names) == 0:
        raise ValueError("No sheets were found in this Excel file.")

    statistics_sheet_name = all_sheet_names[-1]
    statistics_data = pd.read_excel(excel_file, sheet_name=statistics_sheet_name, engine="openpyxl")
    excel_file.close()

    statistics_data.columns = [str(c).strip() for c in statistics_data.columns]

    required_statistics_columns = [
        COL_CYCLE,
        COL_CHARGE_CAPACITY,
        COL_DISCHARGE_CAPACITY,
    ]
    missing = [c for c in required_statistics_columns if c not in statistics_data.columns]
    if missing:
        raise ValueError(
            f"Statistics sheet '{statistics_sheet_name}' is missing required columns: {missing}"
        )

    for col in required_statistics_columns:
        statistics_data[col] = pd.to_numeric(statistics_data[col], errors="coerce")

    statistics_data = statistics_data.dropna(subset=[COL_CYCLE]).copy()
    statistics_data = statistics_data.sort_values(COL_CYCLE).reset_index(drop=True)

    statistics_data[SPECIFIC_CHARGE_COLUMN] = statistics_data[COL_CHARGE_CAPACITY] * 1_000_000 / active_mass_mg
    statistics_data[SPECIFIC_DISCHARGE_COLUMN] = statistics_data[COL_DISCHARGE_CAPACITY] * 1_000_000 / active_mass_mg

    charge_capacity = statistics_data[COL_CHARGE_CAPACITY].to_numpy(dtype=float)
    discharge_capacity = statistics_data[COL_DISCHARGE_CAPACITY].to_numpy(dtype=float)

    ce_values = np.full(len(statistics_data), np.nan, dtype=float)

    if battery_type_name == "Lithium-sulfur battery":
        valid = np.isfinite(charge_capacity) & np.isfinite(discharge_capacity) & (~np.isclose(charge_capacity, 0.0))
        np.divide(discharge_capacity * 100.0, charge_capacity, out=ce_values, where=valid)
    else:
        valid = np.isfinite(charge_capacity) & np.isfinite(discharge_capacity) & (~np.isclose(discharge_capacity, 0.0))
        np.divide(charge_capacity * 100.0, discharge_capacity, out=ce_values, where=valid)

    statistics_data[COULOMBIC_EFFICIENCY_COLUMN] = ce_values

    return all_sheet_names, statistics_sheet_name, statistics_data
