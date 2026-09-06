# =============================================================================
# plotting.py
# Figure builders:
#   build_single_file_figure             -> Module 1 (1 file, many cycles)
#   build_multi_file_figure              -> Module 1 (many files, 1 cycle)
#   build_cycling_stability_figure       -> Module 3 cycling stability / rate
# =============================================================================

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, AutoMinorLocator
from matplotlib.lines import Line2D

from config import (
    COL_STEP, COL_CYCLE, COL_VOLTAGE,
    SPECIFIC_CHARGE_COLUMN, SPECIFIC_DISCHARGE_COLUMN,
    LINE_WIDTH, AXIS_LINE_WIDTH,
)
from capacity_utils import identify_segment_type, get_cycle_colors, ordinal_cycle_name
from excel_reader import COULOMBIC_EFFICIENCY_COLUMN


def _style_axes(ax, all_plotted_capacities, cell_info, title_text,
                use_default_axes, custom_x_min, custom_x_max, custom_y_min, custom_y_max,
                title_fs, axis_label_fs, tick_fs, legend_fs):

    if len(all_plotted_capacities) == 0:
        raise ValueError(
            "No valid capacity data were found for the requested cycle(s)."
        )

    maximum_capacity = np.nanmax(all_plotted_capacities)
    automatic_x_max = maximum_capacity * 1.05

    if automatic_x_max <= 0:
        automatic_x_max = 1.0

    if use_default_axes:
        ax.set_xlim(0, automatic_x_max)
    else:
        if custom_x_min is not None:
            ax.set_xlim(left=custom_x_min)

        ax.set_xlim(
            right=custom_x_max
            if custom_x_max is not None
            else automatic_x_max
        )

    ax.xaxis.set_major_locator(
        MaxNLocator(nbins=6)
    )

    if use_default_axes:
        ax.set_ylim(cell_info["y_limits"])
        ax.set_yticks(cell_info["y_ticks"])
    else:
        ax.set_ylim(custom_y_min, custom_y_max)

    # Exactly 1 minor tick between every pair of major ticks
    ax.xaxis.set_minor_locator(
        AutoMinorLocator(2)
    )
    ax.yaxis.set_minor_locator(
        AutoMinorLocator(2)
    )

    ax.set_xlabel(
        "Specific Capacity (mAh/g)",
        fontsize=axis_label_fs,
    )

    ax.set_ylabel(
        cell_info["y_label"],
        fontsize=axis_label_fs,
    )

    ax.set_title(
        title_text,
        fontsize=title_fs,
        pad=8,
    )

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
        direction="in",
    )

    ax.tick_params(
        axis="both",
        which="minor",
        width=AXIS_LINE_WIDTH * 0.8,
        length=3,
        direction="in",
    )

    ax.grid(False)


def build_single_file_figure(active_data, valid_cycles, cell_info, cell_title_plot,
                             use_default_axes, custom_x_min, custom_x_max, custom_y_min, custom_y_max,
                             title_fs, axis_label_fs, tick_fs, legend_fs,
                             figure_width, figure_height):
    cycle_colors = get_cycle_colors(len(valid_cycles))
    plt.close("all")
    fig, ax = plt.subplots(figsize=(figure_width, figure_height))
    all_plotted_capacities = []
    step_log = []

    for color_number, cycle_number in enumerate(valid_cycles):
        cycle_data = active_data[active_data[COL_CYCLE] == cycle_number].copy()
        cycle_data = cycle_data.sort_values("_Original_Row_Order")
        cycle_data["_Segment_ID"] = cycle_data[COL_STEP].ne(cycle_data[COL_STEP].shift()).cumsum()

        legend_added = False
        for segment_id, segment in cycle_data.groupby("_Segment_ID", sort=False):
            step_index = segment[COL_STEP].iloc[0]
            segment_type = identify_segment_type(segment)
            step_log.append(f"Cycle {cycle_number} — Step {step_index:g} → {segment_type}")

            x_column = SPECIFIC_DISCHARGE_COLUMN if segment_type == "discharge" else SPECIFIC_CHARGE_COLUMN
            plot_data = segment[[x_column, COL_VOLTAGE]].dropna()
            if len(plot_data) < 2:
                continue

            x_values = plot_data[x_column].to_numpy()
            y_values = plot_data[COL_VOLTAGE].to_numpy()
            all_plotted_capacities.extend(x_values)

            line_label = ordinal_cycle_name(cycle_number) if not legend_added else None
            legend_added = True
            ax.plot(x_values, y_values, color=cycle_colors[color_number], linewidth=LINE_WIDTH, label=line_label)

    _style_axes(ax, all_plotted_capacities, cell_info, cell_title_plot,
                use_default_axes, custom_x_min, custom_x_max, custom_y_min, custom_y_max,
                title_fs, axis_label_fs, tick_fs, legend_fs)

    fig.tight_layout()
    return fig, step_log


def build_multi_file_figure(datasets, cycle_number, cell_info,
                            use_default_axes, custom_x_min, custom_x_max, custom_y_min, custom_y_max,
                            title_fs, axis_label_fs, tick_fs, legend_fs,
                            figure_width, figure_height):
    file_colors = get_cycle_colors(len(datasets))
    plt.close("all")
    fig, ax = plt.subplots(figsize=(figure_width, figure_height))
    all_plotted_capacities = []
    step_log = []

    for color_number, dataset in enumerate(datasets):
        label = dataset["label"]
        active_data = dataset["active_data"]

        cycle_data = active_data[active_data[COL_CYCLE] == cycle_number].copy()
        cycle_data = cycle_data.sort_values("_Original_Row_Order")
        cycle_data["_Segment_ID"] = cycle_data[COL_STEP].ne(cycle_data[COL_STEP].shift()).cumsum()

        legend_added = False
        for segment_id, segment in cycle_data.groupby("_Segment_ID", sort=False):
            step_index = segment[COL_STEP].iloc[0]
            segment_type = identify_segment_type(segment)
            step_log.append(f"{label} — Step {step_index:g} → {segment_type}")

            x_column = SPECIFIC_DISCHARGE_COLUMN if segment_type == "discharge" else SPECIFIC_CHARGE_COLUMN
            plot_data = segment[[x_column, COL_VOLTAGE]].dropna()
            if len(plot_data) < 2:
                continue

            x_values = plot_data[x_column].to_numpy()
            y_values = plot_data[COL_VOLTAGE].to_numpy()
            all_plotted_capacities.extend(x_values)

            line_label = label if not legend_added else None
            legend_added = True
            ax.plot(x_values, y_values, color=file_colors[color_number], linewidth=LINE_WIDTH, label=line_label)

    title_text = ordinal_cycle_name(cycle_number)

    _style_axes(ax, all_plotted_capacities, cell_info, title_text,
                use_default_axes, custom_x_min, custom_x_max, custom_y_min, custom_y_max,
                title_fs, axis_label_fs, tick_fs, legend_fs)

    fig.tight_layout()
    return fig, step_log


def build_cycling_stability_figure(
    datasets,
    capacity_mode,
    axis_label_fs,
    tick_fs,
    legend_fs,
    figure_width,
    figure_height,
    rate_blocks=None,
    use_default_axes=True,
    custom_x_min=None,
    custom_x_max=None,
    custom_ce_y_min=None,
    custom_ce_y_max=None,
    custom_capacity_y_min=None,
    custom_capacity_y_max=None,
):
    """
    Build the cycling-stability / rate-capability figure.

    IMPORTANT SYMBOL RULE
    ---------------------
    If BOTH capacities are selected:
        - charge capacity = filled marker
        - discharge capacity = open marker
        - C.E. = open marker
        - universal legend also shows Charge / Discharge style entries

    If ONLY charge OR ONLY discharge is selected:
        - C.E. and capacity use the SAME marker, SAME color, and SAME open style
        - no extra Charge/Discharge style item is added to the legend
        - the bottom Y-axis label explicitly says charge or discharge capacity
    """
    if len(datasets) == 0:
        raise ValueError("No datasets were provided for cycling-stability plotting.")

    plt.close("all")

    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        figsize=(figure_width, figure_height),
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.12},
    )

    colors = get_cycle_colors(len(datasets))
    markers = ["o", "s", "^", "D", "v", "P", "X", "<", ">", "h"]
    all_cycle_values = []

    dataset_handles = []
    style_handles = []

    plot_charge = capacity_mode in ["Specific charge capacity", "Both"]
    plot_discharge = capacity_mode in ["Specific discharge capacity", "Both"]
    only_one_capacity = capacity_mode != "Both"

    for idx, dataset in enumerate(datasets):
        label = dataset["label"]
        stats_df = dataset["statistics_data"].copy()
        color = colors[idx]
        marker = markers[idx % len(markers)]

        x_values = stats_df[COL_CYCLE].to_numpy(dtype=float)
        ce_values = stats_df[COULOMBIC_EFFICIENCY_COLUMN].to_numpy(dtype=float)
        charge_values = stats_df[SPECIFIC_CHARGE_COLUMN].to_numpy(dtype=float)
        discharge_values = stats_df[SPECIFIC_DISCHARGE_COLUMN].to_numpy(dtype=float)

        all_cycle_values.extend(
            x_values[np.isfinite(x_values)]
        )

        # ---------------------------------------------------------------------
        # TOP: Coulombic efficiency
        # ---------------------------------------------------------------------
        ax_top.scatter(
            x_values,
            ce_values,
            s=56,
            marker=marker,
            facecolors="none",
            edgecolors=color,
            linewidths=1.4,
            zorder=3,
        )

        # ---------------------------------------------------------------------
        # BOTTOM: capacity
        # ---------------------------------------------------------------------
        if only_one_capacity:
            # If only one capacity is selected, use the EXACT same visual
            # marker style as the C.E. panel. There is no need to encode
            # charge/discharge by fill because only one capacity exists.
            selected_values = (
                charge_values
                if capacity_mode == "Specific charge capacity"
                else discharge_values
            )

            ax_bottom.scatter(
                x_values,
                selected_values,
                s=56,
                marker=marker,
                facecolors="none",
                edgecolors=color,
                linewidths=1.4,
                zorder=3,
            )

        else:
            # BOTH mode remains exactly as before:
            # charge = filled, discharge = open.
            if plot_charge:
                ax_bottom.scatter(
                    x_values,
                    charge_values,
                    s=56,
                    marker=marker,
                    facecolors=color,
                    edgecolors=color,
                    linewidths=0.8,
                    zorder=3,
                )

            if plot_discharge:
                ax_bottom.scatter(
                    x_values,
                    discharge_values,
                    s=56,
                    marker=marker,
                    facecolors="none",
                    edgecolors=color,
                    linewidths=1.4,
                    zorder=3,
                )

        # Dataset legend symbol uses the same universal open marker/color.
        dataset_handles.append(
            Line2D(
                [0],
                [0],
                marker=marker,
                linestyle="None",
                color="none",
                markerfacecolor="none",
                markeredgecolor=color,
                markeredgewidth=1.4,
                markersize=7,
                label=label,
            )
        )

    if len(all_cycle_values) == 0:
        raise ValueError(
            "No valid cycle-index data were found in the Statistics sheet."
        )

    # -------------------------------------------------------------------------
    # X-axis
    # -------------------------------------------------------------------------
    max_cycle = np.nanmax(all_cycle_values)
    automatic_x_max = max_cycle * 1.02 if max_cycle > 0 else 1.0

    if use_default_axes:
        x_min = 0.0
        x_max = automatic_x_max
    else:
        x_min = 0.0 if custom_x_min is None else custom_x_min
        x_max = automatic_x_max if custom_x_max is None else custom_x_max

    ax_top.set_xlim(x_min, x_max)
    ax_bottom.set_xlim(x_min, x_max)

    ax_bottom.xaxis.set_major_locator(
        MaxNLocator(nbins=8, integer=True)
    )
    ax_bottom.xaxis.set_minor_locator(
        AutoMinorLocator(2)
    )

    # -------------------------------------------------------------------------
    # Optional independent Y-axis limits for this module.
    # -------------------------------------------------------------------------
    if not use_default_axes:
        if custom_ce_y_min is not None:
            ax_top.set_ylim(bottom=custom_ce_y_min)
        if custom_ce_y_max is not None:
            ax_top.set_ylim(top=custom_ce_y_max)

        if custom_capacity_y_min is not None:
            ax_bottom.set_ylim(bottom=custom_capacity_y_min)
        if custom_capacity_y_max is not None:
            ax_bottom.set_ylim(top=custom_capacity_y_max)

    # -------------------------------------------------------------------------
    # Axis labels
    # -------------------------------------------------------------------------
    ax_top.set_ylabel(
        "C.E. (%)",
        fontsize=axis_label_fs,
    )

    if capacity_mode == "Specific charge capacity":
        bottom_y_label = "Specific charge capacity\n(mAh g$^{-1}$)"
    elif capacity_mode == "Specific discharge capacity":
        bottom_y_label = "Specific discharge capacity\n(mAh g$^{-1}$)"
    else:
        bottom_y_label = "Specific capacity\n(mAh g$^{-1}$)"

    ax_bottom.set_ylabel(
        bottom_y_label,
        fontsize=axis_label_fs,
    )

    ax_bottom.set_xlabel(
        "Cycle index",
        fontsize=axis_label_fs,
    )

    # -------------------------------------------------------------------------
    # Remove duplicate middle border/ticks.
    # -------------------------------------------------------------------------
    ax_top.spines["bottom"].set_visible(False)
    ax_bottom.spines["top"].set_visible(False)

    ax_top.tick_params(
        axis="x",
        which="both",
        bottom=False,
        labelbottom=False,
    )

    ax_bottom.tick_params(
        axis="x",
        which="both",
        top=False,
    )

    for ax in [ax_top, ax_bottom]:
        for spine in ax.spines.values():
            if spine.get_visible():
                spine.set_linewidth(AXIS_LINE_WIDTH)

        ax.tick_params(
            axis="both",
            which="major",
            labelsize=tick_fs,
            width=AXIS_LINE_WIDTH,
            length=5,
            direction="in",
        )

        ax.tick_params(
            axis="both",
            which="minor",
            width=AXIS_LINE_WIDTH * 0.8,
            length=3,
            direction="in",
        )

        ax.grid(False)

    # -------------------------------------------------------------------------
    # Rate-capability labels / boundaries.
    # -------------------------------------------------------------------------
    if rate_blocks:
        for i, block in enumerate(rate_blocks):
            start = block["start"]
            end = block["end"]
            label = block["label"]
            x_center = (start + end) / 2.0

            # All rate-current labels stay on exactly the same horizontal row.
            label_row_y = 1.035

            ax_bottom.text(
                x_center,
                label_row_y,
                label,
                transform=ax_bottom.get_xaxis_transform(),
                ha="center",
                va="bottom",
                rotation=0,
                fontsize=max(tick_fs - 3, 7),
                clip_on=False,
            )

            if i < len(rate_blocks) - 1:
                next_start = rate_blocks[i + 1]["start"]
                boundary_x = (end + next_start) / 2.0

                ax_top.axvline(
                    boundary_x,
                    color="0.7",
                    linestyle=(0, (2, 2)),
                    linewidth=1.0,
                    zorder=1,
                )

                ax_bottom.axvline(
                    boundary_x,
                    color="0.7",
                    linestyle=(0, (2, 2)),
                    linewidth=1.0,
                    zorder=1,
                )

    # -------------------------------------------------------------------------
    # ONE universal legend, always inside the bottom plot frame.
    # -------------------------------------------------------------------------
    if capacity_mode == "Both":
        style_handles = [
            Line2D(
                [0], [0],
                marker="o",
                linestyle="None",
                color="none",
                markerfacecolor="black",
                markeredgecolor="black",
                markersize=6,
                label="Charge",
            ),
            Line2D(
                [0], [0],
                marker="o",
                linestyle="None",
                color="none",
                markerfacecolor="none",
                markeredgecolor="black",
                markersize=6,
                label="Discharge",
            ),
        ]
    else:
        # Charge-only / discharge-only mode: no redundant capacity-type item.
        style_handles = []

    legend_handles = dataset_handles + style_handles

    ax_bottom.legend(
        handles=legend_handles,
        loc="best",
        fontsize=legend_fs,
        frameon=False,
    )

    fig.subplots_adjust(
        left=0.14,
        right=0.98,
        top=0.92,
        bottom=0.12,
        hspace=0.12,
    )

    return fig
