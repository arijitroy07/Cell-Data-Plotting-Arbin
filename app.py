# =============================================================================
# app.py
# Thin orchestrator only. Run this one: streamlit run app.py
# =============================================================================

import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from excel_reader import load_and_process
from sidebar import render_sidebar
import single_file_tab
import multi_file_tab
import dqdv_tab
import cycling_stability_tab

st.set_page_config(page_title="Battery Data Analysis Toolkit", layout="wide")


def get_font_family():
    try:
        fm.findfont(
            fm.FontProperties(family="Verdana"),
            fallback_to_default=False,
        )
        return "Verdana"
    except ValueError:
        return "DejaVu Sans"


FONT_FAMILY = get_font_family()

plt.rcParams["font.family"] = FONT_FAMILY
plt.rcParams["mathtext.fontset"] = "custom"
plt.rcParams["mathtext.rm"] = FONT_FAMILY
plt.rcParams["mathtext.it"] = f"{FONT_FAMILY}:italic"
plt.rcParams["mathtext.bf"] = f"{FONT_FAMILY}:bold"
plt.rcParams["mathtext.default"] = "regular"


@st.cache_data(show_spinner=False)
def cached_load_and_process(file_bytes, active_mass_mg):
    return load_and_process(file_bytes, active_mass_mg)


ui = render_sidebar()

if FONT_FAMILY != "Verdana":
    st.sidebar.caption("Verdana not found on server — using DejaVu Sans instead.")


tab1, tab2, tab3, tab4 = st.tabs([
    "Module 1: GCD Plot",
    "Module 2: dQ/dV Plot",
    "Module 3: Cycling Stability / Rate Capability",
    "Module 4: Coming soon",
])

# =============================================================================
# MODULE 1
# =============================================================================
with tab1:
    st.header("Voltage Profile / GCD Plot")

    if not ui["uploaded_files"]:
        st.info("Upload one Excel file or several files in the sidebar.")
    elif ui["is_multi_file"]:
        multi_file_tab.render(ui, cached_load_and_process)
    else:
        single_file_tab.render(ui, cached_load_and_process)

# =============================================================================
# MODULE 2
# =============================================================================
with tab2:
    st.header("Differential Capacity (dQ/dV) Plot")

    if not ui["uploaded_files"]:
        st.info("Upload one Excel file or several files in the sidebar.")
    elif ui["is_multi_file"]:
        dqdv_tab.render_multi(ui, cached_load_and_process)
    else:
        dqdv_tab.render_single(ui, cached_load_and_process)

# =============================================================================
# MODULE 3
# =============================================================================
with tab3:
    st.header("Cycling Stability / Rate Capability")

    if not ui["uploaded_files"]:
        st.info("Upload one or more Excel files in the sidebar.")
    else:
        cycling_stability_tab.render(ui)

with tab4:
    st.info("More analysis modules can be added here later.")
