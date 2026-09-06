# =============================================================================
# dqdv_tab.py
# MODULE 2: DIFFERENTIAL CAPACITY / dQ/dV PLOT
#
# Key rules retained:
#   - dQ/dV is calculated at the EXACT original voltage points.
#   - No midpoint voltage.
#   - No smoothing/interpolation of the original curve.
#
# Improvements in this version:
#   - This tab has its OWN Run button.
#   - This tab has its OWN width / height controls.
#   - Broad/nearby peaks are reduced to the strongest representative peak.
#   - Near-duplicate peak voltages from different curves are labeled only once.
#   - Peak labels are collision-checked and shifted up/down/sideways so they do
#     not overlap each other and remain inside the axes frame.
# =============================================================================

import io

import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

from config import (
    COL_STEP,
    COL_CYCLE,
    COL_VOLTAGE,
    SPECIFIC_CHARGE_COLUMN,
    SPECIFIC_DISCHARGE_COLUMN,
    LINE_WIDTH,
    AXIS_LINE_WIDTH,
    FIGURE_WIDTH,
    FIGURE_HEIGHT,
    DV_ZERO_TOLERANCE,
)
from capacity_utils import (
    identify_segment_type,
    get_cycle_colors,
    ordinal_cycle_name,
    parse_cycle_numbers,
    parse_single_cycle_number,
    prepare_title,
)


# =============================================================================
# CORE dQ/dV CALCULATION
# =============================================================================

def calculate_dqdv_at_original_voltage(q_values, v_values):
    """
    Calculate dQ/dV at the SAME original voltage points used by the GCD plot.
    """
    q_values = np.asarray(q_values, dtype=float)
    v_values = np.asarray(v_values, dtype=float)

    valid_values = np.isfinite(q_values) & np.isfinite(v_values)
    q_values = q_values[valid_values]
    v_values = v_values[valid_values]

    if len(q_values) < 2:
        return v_values, np.full(len(v_values), np.nan)

    dQ = np.gradient(q_values)
    dV = np.gradient(v_values)

    dQdV = np.full(q_values.shape, np.nan, dtype=float)

    valid_derivative = (
        np.isfinite(dQ)
        & np.isfinite(dV)
        & (np.abs(dV) > DV_ZERO_TOLERANCE)
    )

    np.divide(
        dQ,
        dV,
        out=dQdV,
        where=valid_derivative,
    )

    return v_values, dQdV


# =============================================================================
# PEAK DETECTION / REDUCTION
# =============================================================================

def _cluster_peaks_by_voltage(peaks, voltage_tolerance):
    """
    Group nearby peak candidates and keep ONLY the strongest point from each
    group. This is what prevents one broad peak from receiving many labels.
    """
    if not peaks:
        return []

    peaks = sorted(peaks, key=lambda p: p["voltage"])
    clusters = [[peaks[0]]]

    for peak in peaks[1:]:
        if abs(peak["voltage"] - clusters[-1][-1]["voltage"]) <= voltage_tolerance:
            clusters[-1].append(peak)
        else:
            clusters.append([peak])

    representative_peaks = []

    for cluster in clusters:
        best = max(cluster, key=lambda p: abs(p["y"]))
        representative_peaks.append(best)

    return representative_peaks


def find_representative_peaks(
    voltage_array,
    dqdv_array,
    threshold_percent,
    voltage_tolerance,
):
    """
    Find positive and negative peaks independently, apply the relative peak
    threshold, then collapse nearby peak points into one strongest point.
    """
    valid = np.isfinite(voltage_array) & np.isfinite(dqdv_array)
    v = voltage_array[valid]
    y = dqdv_array[valid]

    if len(y) < 3:
        return []

    peaks = []

    # -------------------------------------------------------------------------
    # Positive side
    # -------------------------------------------------------------------------
    pos_idx, _ = find_peaks(y)
    pos_idx = pos_idx[y[pos_idx] > 0]

    positive_candidates = []

    if len(pos_idx) > 0:
        max_positive = y[pos_idx].max()
        threshold = (threshold_percent / 100.0) * max_positive

        for idx in pos_idx[y[pos_idx] >= threshold]:
            positive_candidates.append({
                "voltage": float(v[idx]),
                "y": float(y[idx]),
                "side": "positive",
            })

    peaks.extend(
        _cluster_peaks_by_voltage(
            positive_candidates,
            voltage_tolerance,
        )
    )

    # -------------------------------------------------------------------------
    # Negative side
    # -------------------------------------------------------------------------
    neg_idx, _ = find_peaks(-y)
    neg_idx = neg_idx[y[neg_idx] < 0]

    negative_candidates = []

    if len(neg_idx) > 0:
        max_negative_magnitude = (-y[neg_idx]).max()
        threshold = (threshold_percent / 100.0) * max_negative_magnitude

        for idx in neg_idx[(-y[neg_idx]) >= threshold]:
            negative_candidates.append({
                "voltage": float(v[idx]),
                "y": float(y[idx]),
                "side": "negative",
            })

    peaks.extend(
        _cluster_peaks_by_voltage(
            negative_candidates,
            voltage_tolerance,
        )
    )

    return peaks


def merge_duplicate_peaks_between_curves(peaks, voltage_tolerance):
    """
    If two different datasets have almost the same peak voltage, keep one
    label only. Positive and negative peaks are treated separately.
    """
    if not peaks:
        return []

    merged = []

    for side in ["positive", "negative"]:
        side_peaks = [p for p in peaks if p["side"] == side]

        if not side_peaks:
            continue

        side_peaks = sorted(side_peaks, key=lambda p: p["voltage"])
        clusters = [[side_peaks[0]]]

        for peak in side_peaks[1:]:
            if abs(peak["voltage"] - clusters[-1][-1]["voltage"]) <= voltage_tolerance:
                clusters[-1].append(peak)
            else:
                clusters.append([peak])

        for cluster in clusters:
            # Keep the strongest representative peak among overlapping datasets.
            best = max(cluster, key=lambda p: abs(p["y"]))
            merged.append(best)

    return merged


# =============================================================================
# NON-OVERLAPPING LABEL PLACEMENT
# =============================================================================

def _bbox_inside(inner_bbox, outer_bbox):
    return (
        inner_bbox.x0 >= outer_bbox.x0
        and inner_bbox.y0 >= outer_bbox.y0
        and inner_bbox.x1 <= outer_bbox.x1
        and inner_bbox.y1 <= outer_bbox.y1
    )


def _bbox_overlaps_any(test_bbox, placed_bboxes):
    return any(test_bbox.overlaps(existing) for existing in placed_bboxes)


def place_peak_labels_without_overlap(ax, fig, peaks, tick_fs):
    """
    Place labels using several candidate offsets. A candidate is accepted only
    if its text box is fully inside the axes frame and does not overlap any
    label already placed.
    """
    if not peaks:
        return

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer=renderer)

    placed_bboxes = []

    # Strongest labels get first choice of position.
    peaks = sorted(peaks, key=lambda p: abs(p["y"]), reverse=True)

    for peak in peaks:
        v = peak["voltage"]
        y = peak["y"]
        color = peak["color"]
        side = peak["side"]

        # Mostly vertical shifts, then small lateral shifts if needed.
        if side == "positive":
            candidate_offsets = [
                (0, 10),
                (0, 18),
                (0, 26),
                (12, 12),
                (-12, 12),
                (18, 20),
                (-18, 20),
                (0, -12),
                (12, -12),
                (-12, -12),
            ]
        else:
            candidate_offsets = [
                (0, -10),
                (0, -18),
                (0, -26),
                (12, -12),
                (-12, -12),
                (18, -20),
                (-18, -20),
                (0, 12),
                (12, 12),
                (-12, 12),
            ]

        placed = False

        for dx_points, dy_points in candidate_offsets:
            annotation = ax.annotate(
                f"{v:.2f} V",
                xy=(v, y),
                xytext=(dx_points, dy_points),
                textcoords="offset points",
                ha="center",
                va="center",
                fontsize=max(tick_fs - 2, 7),
                color=color,
                clip_on=True,
                annotation_clip=True,
            )

            fig.canvas.draw()
            bbox = annotation.get_window_extent(renderer=renderer)
            padded_bbox = bbox.expanded(1.06, 1.15)

            if (
                _bbox_inside(padded_bbox, axes_bbox)
                and not _bbox_overlaps_any(padded_bbox, placed_bboxes)
            ):
                placed_bboxes.append(padded_bbox)
                placed = True
                break

            annotation.remove()

        # If every preferred position is occupied, try a slightly larger
        # alternating vertical displacement. Still require it to be inside.
        if not placed:
            emergency_offsets = [
                (0, 34),
                (0, -34),
                (24, 28),
                (-24, 28),
                (24, -28),
                (-24, -28),
            ]

            for dx_points, dy_points in emergency_offsets:
                annotation = ax.annotate(
                    f"{v:.2f} V",
                    xy=(v, y),
                    xytext=(dx_points, dy_points),
                    textcoords="offset points",
                    ha="center",
                    va="center",
                    fontsize=max(tick_fs - 2, 7),
                    color=color,
                    clip_on=True,
                    annotation_clip=True,
                )

                fig.canvas.draw()
                bbox = annotation.get_window_extent(renderer=renderer)
                padded_bbox = bbox.expanded(1.06, 1.15)

                if (
                    _bbox_inside(padded_bbox, axes_bbox)
                    and not _bbox_overlaps_any(padded_bbox, placed_bboxes)
                ):
                    placed_bboxes.append(padded_bbox)
                    placed = True
                    break

                annotation.remove()


# =============================================================================
# FIGURE BUILDER
# =============================================================================

def build_dqdv_figure(
    curves,
    cell_info,
    title_text,
    use_default_axes,
    custom_x_min,
    custom_x_max,
    custom_y_min,
    custom_y_max,
    title_fs,
    axis_label_fs,
    tick_fs,
    legend_fs,
    y_unit_label,
    peak_threshold_percent,
    peak_merge_tolerance_v,
    figure_width,
    figure_height,
):
    plt.close("all")

    fig, ax = plt.subplots(
        figsize=(figure_width, figure_height)
    )

    all_curve_peaks = []

    for curve in curves:
        color = curve["color"]
        label = curve["label"]
        legend_added = False

        combined_v = []
        combined_y = []

        for v_values, y_values in curve["segments"]:
            if len(v_values) == 0:
                continue

            line_label = label if not legend_added else None
            legend_added = True

            ax.plot(
                v_values,
                y_values,
                color=color,
                linewidth=LINE_WIDTH,
                label=line_label,
            )

            combined_v.append(v_values)
            combined_y.append(y_values)

        if combined_v:
            v_all = np.concatenate(combined_v)
            y_all = np.concatenate(combined_y)

            peaks = find_representative_peaks(
                v_all,
                y_all,
                peak_threshold_percent,
                peak_merge_tolerance_v,
            )

            for peak in peaks:
                peak["color"] = color

            all_curve_peaks.extend(peaks)

    # -------------------------------------------------------------------------
    # X-axis = voltage
    # -------------------------------------------------------------------------
    if use_default_axes:
        ax.set_xlim(cell_info["y_limits"])
        ax.set_xticks(cell_info["y_ticks"])
    else:
        x_min = (
            custom_x_min
            if custom_x_min is not None
            else cell_info["y_limits"][0]
        )
        x_max = (
            custom_x_max
            if custom_x_max is not None
            else cell_info["y_limits"][1]
        )
        ax.set_xlim(x_min, x_max)

    # -------------------------------------------------------------------------
    # Y-axis = automatic unless user overrides it
    # -------------------------------------------------------------------------
    if not use_default_axes:
        if custom_y_min is not None:
            ax.set_ylim(bottom=custom_y_min)

        if custom_y_max is not None:
            ax.set_ylim(top=custom_y_max)

    ax.set_xlabel(
        cell_info["y_label"],
        fontsize=axis_label_fs,
    )

    ax.set_ylabel(
        y_unit_label,
        fontsize=axis_label_fs,
    )

    ax.set_title(
        title_text,
        fontsize=title_fs,
        pad=8,
    )

    # Legend is ALWAYS inside the axes frame.
    ax.legend(
        loc="best",
        fontsize=legend_fs,
        frameon=False,
    )

    for spine in ax.spines.values():
        spine.set_linewidth(AXIS_LINE_WIDTH)

    ax.tick_params(
        axis="both",
        which="major",
        labelsize=tick_fs,
        width=AXIS_LINE_WIDTH,
        length=5,
        direction="out",
    )

    ax.grid(False)

    fig.tight_layout()
    fig.canvas.draw()

    # -------------------------------------------------------------------------
    # Remove duplicate labels from near-identical peaks across datasets.
    # -------------------------------------------------------------------------
    merged_peaks = merge_duplicate_peaks_between_curves(
        all_curve_peaks,
        peak_merge_tolerance_v,
    )

    # -------------------------------------------------------------------------
    # Place labels after final axes geometry exists.
    # -------------------------------------------------------------------------
    place_peak_labels_without_overlap(
        ax,
        fig,
        merged_peaks,
        tick_fs,
    )

    return fig


# =============================================================================
# MODULE-SPECIFIC SETTINGS
# =============================================================================

def render_dqdv_settings(key_prefix):
    c1, c2, c3 = st.columns(3)

    with c1:
        y_unit_choice = st.radio(
            "dQ/dV Y-axis unit",
            [
                "mAh·g⁻¹·V⁻¹ (default)",
                "Ah·g⁻¹·V⁻¹ (÷1000)",
            ],
            key=f"{key_prefix}_y_unit",
        )

    with c2:
        peak_threshold_percent = st.number_input(
            "Label peaks above % of highest peak",
            min_value=0.0,
            max_value=100.0,
            value=25.0,
            step=1.0,
            key=f"{key_prefix}_peak_threshold",
        )

    with c3:
        peak_merge_tolerance_v = st.number_input(
            "Merge nearby peak labels within (V)",
            min_value=0.001,
            max_value=1.0,
            value=0.05,
            step=0.01,
            format="%.3f",
            key=f"{key_prefix}_peak_merge_tol",
        )

    if y_unit_choice.startswith("Ah"):
        y_unit_divisor = 1000.0
        y_unit_label = r"dQ/dV ($Ah\,g^{-1}\,V^{-1}$)"
    else:
        y_unit_divisor = 1.0
        y_unit_label = r"dQ/dV ($mAh\,g^{-1}\,V^{-1}$)"

    return (
        y_unit_divisor,
        y_unit_label,
        peak_threshold_percent,
        peak_merge_tolerance_v,
    )


# =============================================================================
# BUILD ONE CURVE'S SEGMENTS
# =============================================================================

def _build_curve_segments(active_data, cycle_number, y_unit_divisor):
    cycle_data = active_data[
        active_data[COL_CYCLE] == cycle_number
    ].copy()

    cycle_data = cycle_data.sort_values("_Original_Row_Order")

    cycle_data["_Segment_ID"] = (
        cycle_data[COL_STEP]
        .ne(cycle_data[COL_STEP].shift())
        .cumsum()
    )

    segments_out = []
    step_log = []

    for segment_id, segment in cycle_data.groupby(
        "_Segment_ID",
        sort=False,
    ):
        step_index = segment[COL_STEP].iloc[0]
        segment_type = identify_segment_type(segment)

        step_log.append(
            f"Step {step_index:g} → {segment_type}"
        )

        x_column = (
            SPECIFIC_DISCHARGE_COLUMN
            if segment_type == "discharge"
            else SPECIFIC_CHARGE_COLUMN
        )

        # EXACT same Q-V pairs as the GCD plot.
        plot_data = segment[[
            x_column,
            COL_VOLTAGE,
        ]].dropna()

        if len(plot_data) < 2:
            continue

        q_values = plot_data[x_column].to_numpy(dtype=float)
        v_values = plot_data[COL_VOLTAGE].to_numpy(dtype=float)

        voltage_for_plot, dqdv_values = (
            calculate_dqdv_at_original_voltage(
                q_values,
                v_values,
            )
        )

        dqdv_values = dqdv_values / y_unit_divisor

        segments_out.append(
            (voltage_for_plot, dqdv_values)
        )

    return segments_out, step_log


# =============================================================================
# OUTPUT PERSISTENCE HELPERS
# =============================================================================

def _show_saved_output(png_key, log_key, download_key, download_name):
    if png_key in st.session_state:
        st.image(st.session_state[png_key])

        st.download_button(
            "Download plot as PNG",
            data=st.session_state[png_key],
            file_name=download_name,
            mime="image/png",
            key=download_key,
        )

        if log_key in st.session_state:
            with st.expander("Charge/discharge segment log"):
                for line in st.session_state[log_key]:
                    st.text(line)


# =============================================================================
# MODULE-SPECIFIC AXIS SETTINGS
# =============================================================================

def _render_dqdv_axis_settings(key_prefix, cell_info):
    """Return axis settings that belong only to this dQ/dV tab/mode."""
    with st.expander("dQ/dV axis settings (optional)"):
        use_default_axes = st.checkbox(
            "Use default dQ/dV axis settings",
            value=True,
            key=f"{key_prefix}_default_axes",
        )

        custom_x_min = None
        custom_x_max = None
        custom_y_min_text = ""
        custom_y_max_text = ""

        if not use_default_axes:
            custom_x_min = st.number_input(
                "dQ/dV X-axis minimum",
                value=float(cell_info["y_limits"][0]),
                key=f"{key_prefix}_x_min",
            )

            custom_x_max = st.number_input(
                "dQ/dV X-axis maximum",
                value=float(cell_info["y_limits"][1]),
                key=f"{key_prefix}_x_max",
            )

            custom_y_min_text = st.text_input(
                "dQ/dV Y-axis minimum (blank = automatic)",
                value="",
                key=f"{key_prefix}_y_min",
            )

            custom_y_max_text = st.text_input(
                "dQ/dV Y-axis maximum (blank = automatic)",
                value="",
                key=f"{key_prefix}_y_max",
            )

    return (
        use_default_axes,
        custom_x_min,
        custom_x_max,
        custom_y_min_text,
        custom_y_max_text,
    )


def _parse_optional_float(value_text, field_name):
    if value_text.strip() == "":
        return None

    try:
        return float(value_text)
    except ValueError:
        raise ValueError(f"{field_name} must be a number or left blank.")


# =============================================================================
# SINGLE-FILE MODE
# =============================================================================

def render_single(ui, cached_load_and_process):
    uploaded_file = ui["uploaded_files"][0]
    cell_info = ui["cell_info"]
    active_mass_mg = ui["active_mass_mg"]
    cell_title = ui["cell_title"]
    cycle_text = ui["cycle_text"]

    png_key = "dqdv_single_png"
    log_key = "dqdv_single_log"
    signature_key = "dqdv_single_signature"

    signature = (uploaded_file.name, uploaded_file.size)

    if st.session_state.get(signature_key) != signature:
        st.session_state.pop(png_key, None)
        st.session_state.pop(log_key, None)
        st.session_state[signature_key] = signature

    (
        y_unit_divisor,
        y_unit_label,
        peak_threshold_percent,
        peak_merge_tolerance_v,
    ) = render_dqdv_settings("dqdv_single")

    st.markdown("**dQ/dV plot size / ratio**")
    c1, c2 = st.columns(2)

    with c1:
        figure_width = st.number_input(
            "dQ/dV plot width",
            min_value=2.0,
            value=float(FIGURE_WIDTH),
            step=0.5,
            key="dqdv_single_width",
        )

    with c2:
        figure_height = st.number_input(
            "dQ/dV plot height",
            min_value=2.0,
            value=float(FIGURE_HEIGHT),
            step=0.5,
            key="dqdv_single_height",
        )

    (
        use_default_axes,
        custom_x_min,
        custom_x_max,
        custom_y_min_text,
        custom_y_max_text,
    ) = _render_dqdv_axis_settings("dqdv_single", cell_info)

    run_clicked = st.button(
        "Run dQ/dV Plot",
        type="primary",
        key="run_dqdv_single",
    )

    if run_clicked:
        st.session_state.pop(png_key, None)
        st.session_state.pop(log_key, None)

        try:
            custom_y_min = None
            custom_y_max = None

            if not use_default_axes:
                custom_y_min = _parse_optional_float(
                    custom_y_min_text,
                    "dQ/dV Y-axis minimum",
                )
                custom_y_max = _parse_optional_float(
                    custom_y_max_text,
                    "dQ/dV Y-axis maximum",
                )

            file_bytes = uploaded_file.getvalue()

            _, _, _, active_data = cached_load_and_process(
                file_bytes,
                active_mass_mg,
            )

            available_cycles = np.sort(
                active_data[COL_CYCLE].dropna().astype(int).unique()
            )

            try:
                selected_cycles = parse_cycle_numbers(cycle_text)
            except ValueError:
                st.error("Enter cycle numbers like: 1, 5, 20, 50")
                return

            valid_cycles = [
                c for c in selected_cycles
                if c in available_cycles
            ]

            missing_cycles = [
                c for c in selected_cycles
                if c not in available_cycles
            ]

            if missing_cycles:
                st.warning(
                    f"These requested cycles were not found: {missing_cycles}"
                )

            if cell_title.strip() == "":
                st.error("Please enter a graph title.")
                return

            if len(valid_cycles) == 0:
                st.error(
                    "None of the requested cycle numbers were found in the dataset."
                )
                return

            cell_title_plot = prepare_title(cell_title)
            colors = get_cycle_colors(len(valid_cycles))

            curves = []
            all_step_logs = []

            for color_number, cycle_number in enumerate(valid_cycles):
                segments, step_log = _build_curve_segments(
                    active_data,
                    cycle_number,
                    y_unit_divisor,
                )

                curves.append({
                    "label": ordinal_cycle_name(cycle_number),
                    "color": colors[color_number],
                    "segments": segments,
                })

                all_step_logs.extend([
                    f"Cycle {cycle_number} — {line}"
                    for line in step_log
                ])

            fig = build_dqdv_figure(
                curves,
                cell_info,
                cell_title_plot,
                use_default_axes,
                custom_x_min,
                custom_x_max,
                custom_y_min,
                custom_y_max,
                ui["title_fs"],
                ui["axis_label_fs"],
                ui["tick_fs"],
                ui["legend_fs"],
                y_unit_label,
                peak_threshold_percent,
                peak_merge_tolerance_v,
                figure_width,
                figure_height,
            )

            buf = io.BytesIO()
            fig.savefig(
                buf,
                format="png",
                dpi=300,
                bbox_inches="tight",
            )

            st.session_state[png_key] = buf.getvalue()
            st.session_state[log_key] = all_step_logs

        except Exception as e:
            st.error(str(e))

    _show_saved_output(
        png_key,
        log_key,
        "download_dqdv_single",
        "dqdv_plot.png",
    )


# =============================================================================
# MULTI-FILE MODE
# =============================================================================

def render_multi(ui, cached_load_and_process):
    uploaded_files = ui["uploaded_files"]
    file_labels = ui["file_labels"]
    file_masses = ui["file_masses"]
    cell_info = ui["cell_info"]
    cycle_text = ui["cycle_text"]

    png_key = "dqdv_multi_png"
    log_key = "dqdv_multi_log"
    signature_key = "dqdv_multi_signature"

    signature = tuple(
        (f.name, f.size)
        for f in uploaded_files
    )

    if st.session_state.get(signature_key) != signature:
        st.session_state.pop(png_key, None)
        st.session_state.pop(log_key, None)
        st.session_state[signature_key] = signature

    (
        y_unit_divisor,
        y_unit_label,
        peak_threshold_percent,
        peak_merge_tolerance_v,
    ) = render_dqdv_settings("dqdv_multi")

    st.markdown("**dQ/dV comparison plot size / ratio**")
    c1, c2 = st.columns(2)

    with c1:
        figure_width = st.number_input(
            "dQ/dV comparison width",
            min_value=2.0,
            value=float(FIGURE_WIDTH),
            step=0.5,
            key="dqdv_multi_width",
        )

    with c2:
        figure_height = st.number_input(
            "dQ/dV comparison height",
            min_value=2.0,
            value=float(FIGURE_HEIGHT),
            step=0.5,
            key="dqdv_multi_height",
        )

    (
        use_default_axes,
        custom_x_min,
        custom_x_max,
        custom_y_min_text,
        custom_y_max_text,
    ) = _render_dqdv_axis_settings("dqdv_multi", cell_info)

    run_clicked = st.button(
        "Run dQ/dV Comparison",
        type="primary",
        key="run_dqdv_multi",
    )

    if run_clicked:
        st.session_state.pop(png_key, None)
        st.session_state.pop(log_key, None)

        try:
            custom_y_min = None
            custom_y_max = None

            if not use_default_axes:
                custom_y_min = _parse_optional_float(
                    custom_y_min_text,
                    "dQ/dV Y-axis minimum",
                )
                custom_y_max = _parse_optional_float(
                    custom_y_max_text,
                    "dQ/dV Y-axis maximum",
                )

            datasets = []

            for idx, f in enumerate(uploaded_files):
                file_bytes = f.getvalue()

                _, _, _, active_data = cached_load_and_process(
                    file_bytes,
                    file_masses[idx],
                )

                datasets.append({
                    "label": file_labels[idx],
                    "active_data": active_data,
                })

            try:
                cycle_number = parse_single_cycle_number(cycle_text)
            except ValueError as e:
                st.error(str(e))
                return

            missing_in = [
                d["label"]
                for d in datasets
                if cycle_number
                not in set(
                    d["active_data"][COL_CYCLE]
                    .dropna()
                    .astype(int)
                    .unique()
                )
            ]

            if missing_in:
                st.warning(
                    f"Cycle {cycle_number} is missing from: {missing_in}"
                )

            colors = get_cycle_colors(len(datasets))
            curves = []
            all_step_logs = []

            for color_number, dataset in enumerate(datasets):
                segments, step_log = _build_curve_segments(
                    dataset["active_data"],
                    cycle_number,
                    y_unit_divisor,
                )

                curves.append({
                    "label": dataset["label"],
                    "color": colors[color_number],
                    "segments": segments,
                })

                all_step_logs.extend([
                    f"{dataset['label']} — {line}"
                    for line in step_log
                ])

            title_text = ordinal_cycle_name(cycle_number)

            fig = build_dqdv_figure(
                curves,
                cell_info,
                title_text,
                use_default_axes,
                custom_x_min,
                custom_x_max,
                custom_y_min,
                custom_y_max,
                ui["title_fs"],
                ui["axis_label_fs"],
                ui["tick_fs"],
                ui["legend_fs"],
                y_unit_label,
                peak_threshold_percent,
                peak_merge_tolerance_v,
                figure_width,
                figure_height,
            )

            buf = io.BytesIO()
            fig.savefig(
                buf,
                format="png",
                dpi=300,
                bbox_inches="tight",
            )

            st.session_state[png_key] = buf.getvalue()
            st.session_state[log_key] = all_step_logs

        except Exception as e:
            st.error(str(e))

    _show_saved_output(
        png_key,
        log_key,
        "download_dqdv_multi",
        "dqdv_comparison_plot.png",
    )
