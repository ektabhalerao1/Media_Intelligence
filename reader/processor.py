from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from reader.extractor import AccessGateError, detect_access_gate, extract_article_text, fetch_html, split_paragraphs
from reader.llm_analyzer import LLMAnalyzer
from reader.search import count_occurrences, find_matching_paragraph_numbers


RESULT_COLUMNS = [
    "URL",
    "Duplicate Record",
    "Search Term",
    "Search Term Found",
    "Number of Occurrences",
    "Paragraph Numbers Containing Matches",
    "Processing Status",
    "Error Message",
    "Article Topic",
    "Is Climate Tech",
    "Brand Sentiment",
    "Sentiment Reason",
    "Confidence Score",
    "Input Sentiment",
    "Output Sentiment",
    "Sentiment Comparison",
]


def process_urls(
    urls: list[str],
    search_term: str,
    input_sentiments: list[str] | None = None,
    duplicate_flags: list[bool] | None = None,
    progress_callback: Callable[[dict[str, str | int]], None] | None = None,
) -> pd.DataFrame:
    """Process each URL and return a results DataFrame for download and display."""
    rows: list[dict[str, str | int]] = []
    total = len(urls)
    llm_analyzer = LLMAnalyzer()
    llm_analyzer.cleanup_expired_cache()

    for index, raw_url in enumerate(urls, start=1):
        url = (raw_url or "").strip()
        input_sentiment = ""
        if input_sentiments and index - 1 < len(input_sentiments):
            input_sentiment = str(input_sentiments[index - 1]).strip()
        is_duplicate = False
        if duplicate_flags and index - 1 < len(duplicate_flags):
            is_duplicate = bool(duplicate_flags[index - 1])

        row: dict[str, str | int] = {
            "URL": url,
            "Duplicate Record": "Yes" if is_duplicate else "No",
            "Search Term": search_term,
            "Search Term Found": "No",
            "Number of Occurrences": 0,
            "Paragraph Numbers Containing Matches": "",
            "Article Topic": "LLM Failed",
            "Is Climate Tech": "LLM Failed",
            "Brand Sentiment": "LLM Failed",
            "Sentiment Reason": "LLM analysis did not run.",
            "Confidence Score": "LLM Failed",
            "Input Sentiment": input_sentiment,
            "Output Sentiment": "LLM Failed",
            "Sentiment Comparison": "Mismatch",
            "Processing Status": "Failed",
            "Error Message": "",
        }

        status_message = ""
        try:
            if not url:
                raise ValueError("Empty URL value.")

            html = fetch_html(url=url, retries=1)
            access_gate = detect_access_gate(html)
            if access_gate:
                raise AccessGateError(access_gate)

            article_text = extract_article_text(html=html, url=url)

            if not article_text.strip():
                raise ValueError("No readable article content could be extracted.")

            paragraphs = split_paragraphs(article_text)
            occurrences = count_occurrences(article_text, search_term)
            paragraph_numbers = find_matching_paragraph_numbers(paragraphs, search_term)

            row["Search Term Found"] = "Yes" if occurrences > 0 else "No"
            row["Number of Occurrences"] = occurrences
            row["Paragraph Numbers Containing Matches"] = ", ".join(map(str, paragraph_numbers))
            row["Processing Status"] = "Success"

            try:
                llm_result = llm_analyzer.analyze(article_text=article_text, search_term=search_term)
                row["Article Topic"] = llm_result.article_topic
                row["Is Climate Tech"] = llm_result.is_climate_tech
                row["Brand Sentiment"] = llm_result.brand_sentiment
                row["Sentiment Reason"] = llm_result.sentiment_reason
                row["Confidence Score"] = llm_result.confidence_score
            except Exception as llm_exc:  # pylint: disable=broad-except
                row["Article Topic"] = "LLM Failed"
                row["Is Climate Tech"] = "LLM Failed"
                row["Brand Sentiment"] = "LLM Failed"
                row["Sentiment Reason"] = f"LLM analysis failed: {llm_exc}"
                row["Confidence Score"] = "LLM Failed"

                if row["Error Message"]:
                    row["Error Message"] = f"{row['Error Message']} | LLM: {llm_exc}"
                else:
                    row["Error Message"] = f"LLM analysis failed: {llm_exc}"

            row["Output Sentiment"] = str(row["Brand Sentiment"])
            row["Sentiment Comparison"] = _compare_sentiments(
                input_sentiment=str(row["Input Sentiment"]),
                output_sentiment=str(row["Output Sentiment"]),
            )

            if occurrences > 0:
                status_message = f"Match found ({occurrences} occurrences)"
            else:
                status_message = "Processed successfully (no matches)"

            if row["Article Topic"] == "LLM Failed":
                status_message = f"{status_message}; LLM failed"
            else:
                status_message = f"{status_message}; LLM analyzed"

        except Exception as exc:  # pylint: disable=broad-except
            row["Error Message"] = str(exc)
            status_message = f"Failed: {exc}"

        rows.append(row)

        if progress_callback is not None:
            progress_callback(
                {
                    "processed": index,
                    "total": total,
                    "url": url,
                    "status": row["Processing Status"],
                    "message": status_message,
                }
            )

    results_df = pd.DataFrame(rows)
    return results_df[RESULT_COLUMNS]


def build_summary_metrics(results_df: pd.DataFrame) -> dict[str, int]:
    """Calculate dashboard metrics shown in the Streamlit UI."""
    total_urls = len(results_df)
    successful = int((results_df["Processing Status"] == "Success").sum())
    failed = int((results_df["Processing Status"] == "Failed").sum())
    matches_found = int((results_df["Search Term Found"] == "Yes").sum())
    matches_not_found = int((results_df["Search Term Found"] == "No").sum())

    return {
        "total_urls": total_urls,
        "processed": total_urls,
        "successful": successful,
        "failed": failed,
        "matches_found": matches_found,
        "matches_not_found": matches_not_found,
    }


def _normalize_sentiment(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"positive", "neutral", "negative"}:
        return normalized
    return normalized


def _compare_sentiments(input_sentiment: str, output_sentiment: str) -> str:
    input_norm = _normalize_sentiment(input_sentiment)
    output_norm = _normalize_sentiment(output_sentiment)

    opposite_extremes = {
        ("positive", "negative"),
        ("negative", "positive"),
    }
    if (input_norm, output_norm) in opposite_extremes:
        return "Mismatch"

    # Neutral is intentionally ignored for mismatch detection.
    return "Match"
