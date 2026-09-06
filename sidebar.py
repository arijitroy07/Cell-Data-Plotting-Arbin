# =============================================================================
# sidebar.py
# Shared input widgets only.
#
# IMPORTANT
# ---------
# Axis settings and plot width/height are NOT global anymore.
# Each analysis tab controls its own:
#   - axis limits
#   - plot width
#   - plot height
#
# Font-size customization remains shared because it is a visual style choice
# common to the whole application.
# =============================================================================

import streamlit as st

from config import (
    CELL_TYPES,
    DEFAULT_TITLE_FONT_SIZE,
    DEFAULT_AXIS_LABEL_FONT_SIZE,
    DEFAULT_TICK_FONT_SIZE,
    DEFAULT_LEGEND_FONT_SIZE,
)


def render_sidebar():
    st.sidebar.title("Battery Data Analysis Toolkit")

    uploaded_files = st.sidebar.file_uploader(
        "Upload Neware-style Excel file(s) (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
    )

    cell_type_name = st.sidebar.selectbox(
        "Battery type",
        list(CELL_TYPES.keys()),
    )
    cell_info = CELL_TYPES[cell_type_name]

    is_multi_file = uploaded_files is not None and len(uploaded_files) > 1

    active_mass_mg = None
    cell_title = None
    cycle_text = None
    file_labels = []
    file_masses = []

    # -------------------------------------------------------------------------
    # SINGLE-FILE MODE
    # -------------------------------------------------------------------------
    if uploaded_files is not None and len(uploaded_files) == 1:
        active_mass_mg = st.sidebar.number_input(
            "Active material mass (mg)",
            min_value=0.0001,
            value=1.0,
            format="%.4f",
        )

        cell_title = st.sidebar.text_input(
            "Graph title",
            value="MoS$_2$",
            help='Use $_2$ for subscript, $^{+}$ for superscript, e.g. MoWS$_2$ NIB',
        )

        cycle_text = st.sidebar.text_input(
            "Cycles to plot (e.g. 1, 20, 25, 35)",
            value="1",
        )

    # -------------------------------------------------------------------------
    # MULTI-FILE MODE
    # -------------------------------------------------------------------------
    elif is_multi_file:
        st.sidebar.markdown(
            "**Multiple files detected** — one legend label + mass per file, one shared cycle."
        )

        for idx, f in enumerate(uploaded_files):
            st.sidebar.markdown(f"—— File {idx + 1}: `{f.name}` ——")

            label = st.sidebar.text_input(
                f"Legend label for file {idx + 1}",
                value=f.name.rsplit(".", 1)[0],
                key=f"label_{idx}",
            )

            mass = st.sidebar.number_input(
                f"Active mass (mg) for file {idx + 1}",
                min_value=0.0001,
                value=1.0,
                format="%.4f",
                key=f"mass_{idx}",
            )

            file_labels.append(label)
            file_masses.append(mass)

        cycle_text = st.sidebar.text_input(
            "Enter the ONE cycle number you want to plot",
            value="1",
        )

    # -------------------------------------------------------------------------
    # SHARED FONT CUSTOMIZATION ONLY
    # -------------------------------------------------------------------------
    with st.sidebar.expander("Font customization (optional)"):
        customize_fonts = st.checkbox(
            "Customize font sizes",
            value=False,
        )

        if customize_fonts:
            title_fs = st.number_input(
                "Title font size",
                value=float(DEFAULT_TITLE_FONT_SIZE),
            )

            axis_label_fs = st.number_input(
                "Axis-label font size",
                value=float(DEFAULT_AXIS_LABEL_FONT_SIZE),
            )

            tick_fs = st.number_input(
                "Tick-label font size",
                value=float(DEFAULT_TICK_FONT_SIZE),
            )

            legend_fs = st.number_input(
                "Legend font size",
                value=float(DEFAULT_LEGEND_FONT_SIZE),
            )

        else:
            title_fs = DEFAULT_TITLE_FONT_SIZE
            axis_label_fs = DEFAULT_AXIS_LABEL_FONT_SIZE
            tick_fs = DEFAULT_TICK_FONT_SIZE
            legend_fs = DEFAULT_LEGEND_FONT_SIZE

    return {
        "uploaded_files": uploaded_files,
        "is_multi_file": is_multi_file,
        "cell_type_name": cell_type_name,
        "cell_info": cell_info,
        "active_mass_mg": active_mass_mg,
        "cell_title": cell_title,
        "cycle_text": cycle_text,
        "file_labels": file_labels,
        "file_masses": file_masses,
        "title_fs": title_fs,
        "axis_label_fs": axis_label_fs,
        "tick_fs": tick_fs,
        "legend_fs": legend_fs,
    }
