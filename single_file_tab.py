# =============================================================================
# single_file_tab.py
# Module 1, exactly ONE file:
# many cycles, one file, cycle = legend entry.
#
# This tab has its OWN:
#   - Run button
#   - plot width / height controls
#   - axis customization
# =============================================================================

import io

import numpy as np
import streamlit as st

from config import COL_CYCLE, FIGURE_WIDTH, FIGURE_HEIGHT
from capacity_utils import parse_cycle_numbers, prepare_title
from plotting import build_single_file_figure


STATE_PNG = "gcd_single_png"
STATE_LOG = "gcd_single_log"
STATE_SIGNATURE = "gcd_single_signature"


def _current_signature(uploaded_file):
    return (uploaded_file.name, uploaded_file.size)


def _show_saved_output():
    if STATE_PNG in st.session_state:
        st.image(st.session_state[STATE_PNG])

        st.download_button(
            "Download plot as PNG",
            data=st.session_state[STATE_PNG],
            file_name="gcd_plot.png",
            mime="image/png",
            key="download_gcd_single",
        )

        if STATE_LOG in st.session_state:
            with st.expander("Charge/discharge segment log"):
                for line in st.session_state[STATE_LOG]:
                    st.text(line)


def render(ui, cached_load_and_process):
    uploaded_file = ui["uploaded_files"][0]
    cell_info = ui["cell_info"]
    active_mass_mg = ui["active_mass_mg"]
    cell_title = ui["cell_title"]
    cycle_text = ui["cycle_text"]

    signature = _current_signature(uploaded_file)
    if st.session_state.get(STATE_SIGNATURE) != signature:
        st.session_state.pop(STATE_PNG, None)
        st.session_state.pop(STATE_LOG, None)
        st.session_state[STATE_SIGNATURE] = signature

    # -------------------------------------------------------------------------
    # Module-specific plot ratio / size.
    # -------------------------------------------------------------------------
    st.markdown("**GCD plot size / ratio**")
    c1, c2 = st.columns(2)

    with c1:
        figure_width = st.number_input(
            "GCD plot width",
            min_value=2.0,
            value=float(FIGURE_WIDTH),
            step=0.5,
            key="gcd_single_width",
        )

    with c2:
        figure_height = st.number_input(
            "GCD plot height",
            min_value=2.0,
            value=float(FIGURE_HEIGHT),
            step=0.5,
            key="gcd_single_height",
        )

    # -------------------------------------------------------------------------
    # Module-specific axis settings.
    # -------------------------------------------------------------------------
    with st.expander("GCD axis settings (optional)"):
        use_default_axes = st.checkbox(
            "Use default GCD axis settings",
            value=True,
            key="gcd_single_default_axes",
        )

        custom_x_min = None
        custom_x_max_text = ""
        custom_y_min = None
        custom_y_max = None

        if not use_default_axes:
            custom_x_min = st.number_input(
                "GCD X-axis minimum",
                value=0.0,
                key="gcd_single_x_min",
            )

            custom_x_max_text = st.text_input(
                "GCD X-axis maximum (blank = automatic)",
                value="",
                key="gcd_single_x_max",
            )

            custom_y_min = st.number_input(
                "GCD Y-axis minimum",
                value=float(cell_info["y_limits"][0]),
                key="gcd_single_y_min",
            )

            custom_y_max = st.number_input(
                "GCD Y-axis maximum",
                value=float(cell_info["y_limits"][1]),
                key="gcd_single_y_max",
            )

    run_clicked = st.button(
        "Run GCD Plot",
        type="primary",
        key="run_gcd_single",
    )

    if run_clicked:
        st.session_state.pop(STATE_PNG, None)
        st.session_state.pop(STATE_LOG, None)

        try:
            custom_x_max = None
            if not use_default_axes and custom_x_max_text.strip() != "":
                try:
                    custom_x_max = float(custom_x_max_text)
                except ValueError:
                    st.error("GCD X-axis maximum must be a number or left blank.")
                    return

            file_bytes = uploaded_file.getvalue()

            all_sheet_names, raw_data_sheets, battery_data, active_data = (
                cached_load_and_process(file_bytes, active_mass_mg)
            )

            available_cycles = np.sort(
                active_data[COL_CYCLE].dropna().astype(int).unique()
            )

            try:
                selected_cycles = parse_cycle_numbers(cycle_text)
            except ValueError:
                st.error("Enter cycle numbers like: 1, 5, 20, 50")
                return

            valid_cycles = [c for c in selected_cycles if c in available_cycles]
            missing_cycles = [c for c in selected_cycles if c not in available_cycles]

            if missing_cycles:
                st.warning(f"These requested cycles were not found: {missing_cycles}")

            if cell_title.strip() == "":
                st.error("Please enter a graph title.")
                return

            if len(valid_cycles) == 0:
                st.error("None of the requested cycle numbers were found in the dataset.")
                return

            cell_title_plot = prepare_title(cell_title)

            fig, step_log = build_single_file_figure(
                active_data,
                valid_cycles,
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
                figure_width,
                figure_height,
            )

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")

            st.session_state[STATE_PNG] = buf.getvalue()
            st.session_state[STATE_LOG] = step_log

            with st.expander("Sheets read from workbook"):
                st.write("All sheets found:", all_sheet_names)
                st.write("Raw data sheets used:", raw_data_sheets)

            if len(available_cycles) > 0:
                st.caption(
                    f"Available cycles: {int(available_cycles.min())} to {int(available_cycles.max())}"
                )

        except Exception as e:
            st.error(str(e))

    _show_saved_output()
