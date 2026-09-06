# =============================================================================
# multi_file_tab.py
# Module 1, MULTIPLE files:
# one cycle, many files, file = legend entry.
#
# This tab has its OWN:
#   - Run button
#   - plot width / height controls
#   - axis customization
# =============================================================================

import io

import streamlit as st

from config import COL_CYCLE, FIGURE_WIDTH, FIGURE_HEIGHT
from capacity_utils import parse_single_cycle_number
from plotting import build_multi_file_figure


STATE_PNG = "gcd_multi_png"
STATE_LOG = "gcd_multi_log"
STATE_SIGNATURE = "gcd_multi_signature"


def _current_signature(uploaded_files):
    return tuple((f.name, f.size) for f in uploaded_files)


def _show_saved_output():
    if STATE_PNG in st.session_state:
        st.image(st.session_state[STATE_PNG])

        st.download_button(
            "Download plot as PNG",
            data=st.session_state[STATE_PNG],
            file_name="gcd_comparison_plot.png",
            mime="image/png",
            key="download_gcd_multi",
        )

        if STATE_LOG in st.session_state:
            with st.expander("Charge/discharge segment log"):
                for line in st.session_state[STATE_LOG]:
                    st.text(line)


def render(ui, cached_load_and_process):
    uploaded_files = ui["uploaded_files"]
    file_labels = ui["file_labels"]
    file_masses = ui["file_masses"]
    cell_info = ui["cell_info"]
    cycle_text = ui["cycle_text"]

    signature = _current_signature(uploaded_files)
    if st.session_state.get(STATE_SIGNATURE) != signature:
        st.session_state.pop(STATE_PNG, None)
        st.session_state.pop(STATE_LOG, None)
        st.session_state[STATE_SIGNATURE] = signature

    st.markdown("**GCD comparison plot size / ratio**")
    c1, c2 = st.columns(2)

    with c1:
        figure_width = st.number_input(
            "GCD comparison width",
            min_value=2.0,
            value=float(FIGURE_WIDTH),
            step=0.5,
            key="gcd_multi_width",
        )

    with c2:
        figure_height = st.number_input(
            "GCD comparison height",
            min_value=2.0,
            value=float(FIGURE_HEIGHT),
            step=0.5,
            key="gcd_multi_height",
        )

    with st.expander("GCD comparison axis settings (optional)"):
        use_default_axes = st.checkbox(
            "Use default GCD comparison axis settings",
            value=True,
            key="gcd_multi_default_axes",
        )

        custom_x_min = None
        custom_x_max_text = ""
        custom_y_min = None
        custom_y_max = None

        if not use_default_axes:
            custom_x_min = st.number_input(
                "GCD comparison X-axis minimum",
                value=0.0,
                key="gcd_multi_x_min",
            )

            custom_x_max_text = st.text_input(
                "GCD comparison X-axis maximum (blank = automatic)",
                value="",
                key="gcd_multi_x_max",
            )

            custom_y_min = st.number_input(
                "GCD comparison Y-axis minimum",
                value=float(cell_info["y_limits"][0]),
                key="gcd_multi_y_min",
            )

            custom_y_max = st.number_input(
                "GCD comparison Y-axis maximum",
                value=float(cell_info["y_limits"][1]),
                key="gcd_multi_y_max",
            )

    run_clicked = st.button(
        "Run GCD Comparison",
        type="primary",
        key="run_gcd_multi",
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
                    st.error("GCD comparison X-axis maximum must be a number or left blank.")
                    return

            datasets = []
            common_available_cycles = None

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

                these_cycles = set(
                    active_data[COL_CYCLE].dropna().astype(int).unique()
                )

                common_available_cycles = (
                    these_cycles
                    if common_available_cycles is None
                    else common_available_cycles & these_cycles
                )

            try:
                cycle_number = parse_single_cycle_number(cycle_text)
            except ValueError as e:
                st.error(str(e))
                return

            missing_in = [
                d["label"]
                for d in datasets
                if cycle_number
                not in set(d["active_data"][COL_CYCLE].dropna().astype(int).unique())
            ]

            if missing_in:
                st.warning(f"Cycle {cycle_number} is missing from: {missing_in}")

            fig, step_log = build_multi_file_figure(
                datasets,
                cycle_number,
                cell_info,
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

        except Exception as e:
            st.error(str(e))

    _show_saved_output()
