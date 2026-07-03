from __future__ import annotations

from collections import deque

import streamlit as st
from dotenv import load_dotenv

from reader.file_handler import (
    get_input_sentiments,
    has_sentiment_column,
    read_uploaded_file,
    results_to_excel_bytes,
    validate_url_column,
)
from reader.processor import build_summary_metrics, process_urls


load_dotenv()


def _render_header() -> None:
    st.set_page_config(page_title="Article Keyword Search", page_icon="🔎", layout="wide")
    st.title("Article Keyword Search Automation")
    st.caption(
        "Upload a CSV/XLSX with a URL column, search for a term across article content, "
        "and download a processing report."
    )


def _render_metrics(summary: dict[str, int]) -> None:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total URLs", summary["total_urls"])
    c2.metric("Processed", summary["processed"])
    c3.metric("Successful", summary["successful"])
    c4.metric("Failed", summary["failed"])
    c5.metric("Matches Found", summary["matches_found"])
    c6.metric("Matches Not Found", summary["matches_not_found"])


def main() -> None:
    _render_header()

    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    search_term = st.text_input("Search Term", placeholder="Enter keyword or phrase")

    input_df = None
    file_error = None
    if uploaded_file is not None:
        try:
            input_df = read_uploaded_file(uploaded_file)
            validate_url_column(input_df)
        except Exception as exc:  # pylint: disable=broad-except
            file_error = str(exc)

    column_options = ["-- None --"]
    if input_df is not None:
        column_options.extend([str(col) for col in input_df.columns])

    st.markdown("**Duplicate Detection Columns**")
    col1, col2, col3 = st.columns(3)
    duplicate_col_1 = col1.selectbox("Duplicate Column 1", options=column_options, index=0)
    duplicate_col_2 = col2.selectbox("Duplicate Column 2", options=column_options, index=0)
    duplicate_col_3 = col3.selectbox("Duplicate Column 3", options=column_options, index=0)

    start_processing = st.button("Start Processing", type="primary")

    if not start_processing:
        return

    if uploaded_file is None:
        st.error("Please upload a CSV or Excel file before processing.")
        return

    if not search_term.strip():
        st.error("Please provide a search term.")
        return

    if input_df is None:
        st.error(f"Unable to read input file: {file_error or 'Unknown error'}")
        return

    urls = input_df["URL"].fillna("").astype(str).tolist()
    input_sentiments = get_input_sentiments(input_df)

    selected_duplicate_columns = []
    for selected in [duplicate_col_1, duplicate_col_2, duplicate_col_3]:
        if selected != "-- None --" and selected not in selected_duplicate_columns:
            selected_duplicate_columns.append(selected)

    duplicate_flags = [False] * len(input_df)
    if selected_duplicate_columns:
        duplicate_mask = input_df.duplicated(subset=selected_duplicate_columns, keep=False)
        duplicate_flags = duplicate_mask.fillna(False).astype(bool).tolist()
        duplicate_count = int(duplicate_mask.sum())
        st.info(
            f"Detected {duplicate_count} duplicate record(s) using columns: "
            f"{', '.join(selected_duplicate_columns)}"
        )

    total_urls = len(urls)
    if total_urls == 0:
        st.error("The file does not contain any rows to process.")
        return

    if not has_sentiment_column(input_df):
        st.warning('Input file has no "Sentiment" column; comparison fields will be marked as Mismatch.')

    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    live_log_placeholder = st.empty()
    live_messages: deque[str] = deque(maxlen=12)

    def on_progress(update: dict[str, str | int]) -> None:
        processed = int(update["processed"])
        url = str(update["url"])
        status = str(update["status"])
        message = str(update["message"])
        ratio = min(processed / total_urls, 1.0)

        progress_bar.progress(ratio)
        status_placeholder.info(f"Processing {processed}/{total_urls}: {url}")

        live_messages.appendleft(f"{processed}/{total_urls} | {status} | {message}")
        live_log_placeholder.code("\n".join(live_messages), language="text")

    with st.spinner("Processing URLs..."):
        results_df = process_urls(
            urls=urls,
            search_term=search_term.strip(),
            input_sentiments=input_sentiments,
            duplicate_flags=duplicate_flags,
            progress_callback=on_progress,
        )

    progress_bar.progress(1.0)
    st.success("Processing completed.")

    summary = build_summary_metrics(results_df)
    _render_metrics(summary)

    st.subheader("Results")
    st.dataframe(results_df, use_container_width=True)

    output_bytes = results_to_excel_bytes(results_df)
    st.download_button(
        label="Download Results",
        data=output_bytes,
        file_name="article_keyword_search_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    main()
