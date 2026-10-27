"""Streamlit landing page for the project foundation."""

import streamlit as st


def render_dashboard() -> None:
    """Render the current application status and planned workflow."""
    st.set_page_config(page_title="AIOps Log Anomaly Platform", page_icon="📊")
    st.title("AIOps Log Anomaly Detection")
    st.caption("Log analysis and alert grouping platform")

    st.info(
        "Project foundation is ready. Log upload, anomaly detection, and alert "
        "grouping are not implemented yet."
    )

    st.subheader("Planned analysis workflow")
    st.write(
        "Log input → validation → preprocessing → TF-IDF features → "
        "anomaly detection → alert grouping"
    )
    st.write(
        "An anomaly is a signal for investigation; it is not confirmation of an "
        "incident, attack, or root cause."
    )
