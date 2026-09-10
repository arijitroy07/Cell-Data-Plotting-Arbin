# =============================================================================
# cycling_stability_tab.py
# Module 3: Cycling stability / Rate capability.
#
# Reads ONLY the last sheet (Statistics).
# Top    -> Coulombic efficiency vs cycle index
# Bottom -> specific charge capacity and/or specific discharge capacity
#
# This tab has its OWN:
#   - Run button
#   - plot width / height controls
#   - axis customization
#   - cycling-stability / rate-capability mode
#   - persistent output until this tab is run again
# =============================================================================

import io
import re

import streamlit as st
from matplotlib.ticker import AutoMinorLocator

from config import FIGURE_WIDTH, FIGURE_HEIGHT
from excel_reader import load_statistics_and_process
from plotting import build_cycling_stability_figure


STATE_PNG = "cycling_rate_png"
STATE_SIGNATURE = "cycling_rate_signature"
STATE_FILENAME = "cycling_rate_download_name"


def _current_signature(uploaded_files):
    return tuple((f.name, f.size) for f in uploaded_files)


def _parse_rate_blocks(rate_text):
    """
    Expected format, one line per cycle block:

        1-5 = 100
        6-10 = 200
        11-15 = 500
        16-20 = 1000

    Numeric values are shown on one common horizontal row in the figure.
    """
    blocks = []

    lines = [
        line.strip()
        for line in rate_text.splitlines()
        if line.strip() != ""
    ]

    if len(lines) == 0:
        return blocks

    pattern = re.compile(
        r"^(\d+)\s*-\s*(\d+)\s*=\s*(.+)$"
    )

    for line in lines:
        match = pattern.match(line)

        if not match:
            raise ValueError(
                "Each rate line must look like: 1-5 = 100"
            )

        start = int(match.group(1))
        end = int(match.group(2))
        label = match.group(3).strip()

        if start > end:
            raise ValueError(
                f"Invalid rate block '{line}': start cycle cannot be greater than end cycle."
            )

        is_numeric = bool(re.fullmatch(r"[-+]?\d*\.?\d+", label))

        blocks.append({
            "start": start,
            "end": end,
            "label": label,
            "is_numeric": is_numeric,
        })

    # Keep the publication-style format used in the previous version:
    # numerical rate values are shown as 100, 200, 500, ... and the unit
    # is appended once to the final numerical block.
    numeric_indices = [
        i for i, block in enumerate(blocks)
        if block.get("is_numeric", False)
    ]

    if numeric_indices:
        last_numeric_index = numeric_indices[-1]
        blocks[last_numeric_index]["label"] = (
            f"{blocks[last_numeric_index]['label']} mA g$^{{-1}}$"
        )

    return blocks


def _parse_optional_float(value_text, field_name):
    if value_text.strip() == "":
        return None

    try:
        return float(value_text)
    except ValueError:
        raise ValueError(
            f"{field_name} must be a number or left blank."
        )


def _show_saved_output():
    if STATE_PNG in st.session_state:
        st.image(st.session_state[STATE_PNG])

        st.download_button(
            "Download plot as PNG",
            data=st.session_state[STATE_PNG],
            file_name=st.session_state.get(
                STATE_FILENAME,
                "cycling_stability_plot.png",
            ),
            mime="image/png",
            key="download_cycling_rate",
        )


def render(ui):
    uploaded_files = ui["uploaded_files"]
    cell_type_name = ui["cell_type_name"]

    if not uploaded_files:
        st.info("Upload one or more Excel files in the sidebar.")
        return

    signature = _current_signature(uploaded_files)

    if st.session_state.get(STATE_SIGNATURE) != signature:
        st.session_state.pop(STATE_PNG, None)
        st.session_state.pop(STATE_FILENAME, None)
        st.session_state[STATE_SIGNATURE] = signature

    # -------------------------------------------------------------------------
    # Analysis settings. Changing them does NOT run the analysis.
    # -------------------------------------------------------------------------
    analysis_mode = st.radio(
        "Plot mode",
        [
            "Cycling stability",
            "Rate capability",
        ],
        horizontal=True,
        key="cycling_mode",
    )

    capacity_mode = st.radio(
        "Capacity to plot in the bottom part",
        [
            "Specific discharge capacity",
            "Specific charge capacity",
            "Both",
        ],
        horizontal=True,
        key="cycling_capacity_mode",
    )

    # -------------------------------------------------------------------------
    # Rate-capability cycle blocks.
    # -------------------------------------------------------------------------
    rate_blocks = None

    if analysis_mode == "Rate capability":
        rate_text = st.text_area(
            "Rate blocks: one line per cycle range (example: 1-5 = 100)",
            value=(
                "1-5 = 100\n"
                "6-10 = 200\n"
                "11-15 = 500\n"
                "16-20 = 1000"
            ),
            height=140,
            key="rate_blocks_input",
        )

        try:
            rate_blocks = _parse_rate_blocks(rate_text)
        except Exception as e:
            st.error(str(e))
            rate_blocks = None

    # -------------------------------------------------------------------------
    # This module's OWN plot size / ratio.
    # -------------------------------------------------------------------------
    st.markdown("**Cycling stability / rate-capability plot size / ratio**")

    c1, c2 = st.columns(2)

    with c1:
        figure_width = st.number_input(
            "Cycling / rate plot width",
            min_value=2.0,
            value=float(FIGURE_WIDTH + 7.0),
            step=0.5,
            key="cycling_plot_width",
        )

    with c2:
        figure_height = st.number_input(
            "Cycling / rate plot height",
            min_value=3.0,
            value=float(FIGURE_HEIGHT + 1.0),
            step=0.5,
            key="cycling_plot_height",
        )

    # -------------------------------------------------------------------------
    # This module's OWN axis settings.
    # There are two Y axes because the figure contains two stacked panels.
    # -------------------------------------------------------------------------
    with st.expander("Cycling stability / rate-capability axis settings (optional)"):
        use_default_axes = st.checkbox(
            "Use default cycling / rate axis settings",
            value=True,
            key="cycling_default_axes",
        )

        custom_x_min = None
        custom_x_max_text = ""
        custom_ce_y_min_text = ""
        custom_ce_y_max_text = ""
        custom_capacity_y_min_text = ""
        custom_capacity_y_max_text = ""

        if not use_default_axes:
            custom_x_min = st.number_input(
                "Cycle-index X-axis minimum",
                value=0.0,
                key="cycling_x_min",
            )

            custom_x_max_text = st.text_input(
                "Cycle-index X-axis maximum (blank = automatic)",
                value="",
                key="cycling_x_max",
            )

            c3, c4 = st.columns(2)
            with c3:
                custom_ce_y_min_text = st.text_input(
                    "C.E. Y-axis minimum (blank = automatic)",
                    value="",
                    key="cycling_ce_y_min",
                )
                custom_capacity_y_min_text = st.text_input(
                    "Capacity Y-axis minimum (blank = automatic)",
                    value="",
                    key="cycling_capacity_y_min",
                )

            with c4:
                custom_ce_y_max_text = st.text_input(
                    "C.E. Y-axis maximum (blank = automatic)",
                    value="",
                    key="cycling_ce_y_max",
                )
                custom_capacity_y_max_text = st.text_input(
                    "Capacity Y-axis maximum (blank = automatic)",
                    value="",
                    key="cycling_capacity_y_max",
                )

    st.caption(
        "Changing these settings does not rerun the analysis. "
        "Click the Run button when you are ready to update this plot."
    )

    run_clicked = st.button(
        "Run Cycling Stability / Rate Capability",
        type="primary",
        key="run_cycling_rate",
    )

    # -------------------------------------------------------------------------
    # Read files / calculate / plot ONLY after this tab's button is clicked.
    # -------------------------------------------------------------------------
    if run_clicked:
        st.session_state.pop(STATE_PNG, None)
        st.session_state.pop(STATE_FILENAME, None)

        if analysis_mode == "Rate capability" and rate_blocks is None:
            st.error("Please correct the rate-block input before running.")
            _show_saved_output()
            return

        try:
            custom_x_max = None
            custom_ce_y_min = None
            custom_ce_y_max = None
            custom_capacity_y_min = None
            custom_capacity_y_max = None

            if not use_default_axes:
                custom_x_max = _parse_optional_float(
                    custom_x_max_text,
                    "Cycle-index X-axis maximum",
                )
                custom_ce_y_min = _parse_optional_float(
                    custom_ce_y_min_text,
                    "C.E. Y-axis minimum",
                )
                custom_ce_y_max = _parse_optional_float(
                    custom_ce_y_max_text,
                    "C.E. Y-axis maximum",
                )
                custom_capacity_y_min = _parse_optional_float(
                    custom_capacity_y_min_text,
                    "Capacity Y-axis minimum",
                )
                custom_capacity_y_max = _parse_optional_float(
                    custom_capacity_y_max_text,
                    "Capacity Y-axis maximum",
                )

            datasets = []
            sheets_info = []

            # -----------------------------------------------------------------
            # One file
            # -----------------------------------------------------------------
            if len(uploaded_files) == 1:
                active_mass_mg = ui["active_mass_mg"]
                label = uploaded_files[0].name.rsplit(".", 1)[0]

                (
                    all_sheet_names,
                    statistics_sheet_name,
                    statistics_data,
                ) = load_statistics_and_process(
                    uploaded_files[0].getvalue(),
                    active_mass_mg,
                    cell_type_name,
                )

                datasets.append({
                    "label": label,
                    "statistics_data": statistics_data,
                })

                sheets_info.append({
                    "file_name": uploaded_files[0].name,
                    "all_sheet_names": all_sheet_names,
                    "statistics_sheet_name": statistics_sheet_name,
                })

            # -----------------------------------------------------------------
            # Multiple files
            # -----------------------------------------------------------------
            else:
                for idx, uploaded_file in enumerate(uploaded_files):
                    label = ui["file_labels"][idx]
                    active_mass_mg = ui["file_masses"][idx]

                    (
                        all_sheet_names,
                        statistics_sheet_name,
                        statistics_data,
                    ) = load_statistics_and_process(
                        uploaded_file.getvalue(),
                        active_mass_mg,
                        cell_type_name,
                    )

                    datasets.append({
                        "label": label,
                        "statistics_data": statistics_data,
                    })

                    sheets_info.append({
                        "file_name": uploaded_file.name,
                        "all_sheet_names": all_sheet_names,
                        "statistics_sheet_name": statistics_sheet_name,
                    })

            fig = build_cycling_stability_figure(
                datasets=datasets,
                capacity_mode=capacity_mode,
                axis_label_fs=ui["axis_label_fs"],
                tick_fs=ui["tick_fs"],
                legend_fs=ui["legend_fs"],
                figure_width=figure_width,
                figure_height=figure_height,
                rate_blocks=(
                    rate_blocks
                    if analysis_mode == "Rate capability"
                    else None
                ),
                use_default_axes=use_default_axes,
                custom_x_min=custom_x_min,
                custom_x_max=custom_x_max,
                custom_ce_y_min=custom_ce_y_min,
                custom_ce_y_max=custom_ce_y_max,
                custom_capacity_y_min=custom_capacity_y_min,
                custom_capacity_y_max=custom_capacity_y_max,
            )


            ax_top, ax_bottom = fig.axes[:2]

            # Exactly 1 minor tick between major ticks on BOTH Y axes
            ax_top.yaxis.set_minor_locator(AutoMinorLocator(2))
            ax_bottom.yaxis.set_minor_locator(AutoMinorLocator(2))


            buf = io.BytesIO()

            fig.savefig(
                buf,
                format="png",
                dpi=300,
                bbox_inches="tight",
            )

            st.session_state[STATE_PNG] = buf.getvalue()

            st.session_state[STATE_FILENAME] = (
                "rate_capability_plot.png"
                if analysis_mode == "Rate capability"
                else "cycling_stability_plot.png"
            )

            with st.expander("Sheets read from workbook"):
                for info in sheets_info:
                    st.write(f"**File:** {info['file_name']}")
                    st.write(
                        "All sheets found:",
                        info["all_sheet_names"],
                    )
                    st.write(
                        "Statistics sheet used:",
                        info["statistics_sheet_name"],
                    )

        except Exception as e:
            st.error(str(e))

    _show_saved_output()
