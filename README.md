# Article Keyword Search (Streamlit)

Production-ready prototype Streamlit app for searching a user-provided keyword across article URLs from CSV or Excel input.

## What It Does

- Accepts CSV or XLSX upload.
- Validates required `URL` column.
- Provides three dropdown selectors to choose columns used for duplicate detection.
- Processes each URL independently (never stops the batch because one URL fails).
- Fetches pages with `requests` and retries once on failure.
- Extracts readable text using `trafilatura`.
- Falls back to `BeautifulSoup` extraction when Trafilatura does not return usable content.
- Splits article text into paragraphs.
- Performs case-insensitive keyword search across full article text.
- Counts total occurrences.
- Captures paragraph numbers containing matches.
- Runs LLM analysis on successfully extracted article text.
- Adds topic, climate-tech classification, brand sentiment, reason, and confidence score.
- Compares uploaded input sentiment with generated output sentiment.
- Adds Input Sentiment, Output Sentiment, and Sentiment Comparison fields.
- Caches LLM results by article content hash for 10 days.
- Shows real-time processing progress and status in the UI.
- Displays summary metrics and provides downloadable Excel results.

## Output Report Columns

- `URL`
- `Duplicate Record`
- `Search Term`
- `Search Term Found (Yes/No)`
- `Number of Occurrences`
- `Paragraph Numbers Containing Matches`
- `Processing Status (Success/Failed)`
- `Error Message`
- `Article Topic`
- `Is Climate Tech`
- `Brand Sentiment`
- `Sentiment Reason`
- `Confidence Score`
- `Input Sentiment`
- `Output Sentiment`
- `Sentiment Comparison`

## Project Structure

```
.
├── app.py
├── reader
│   ├── __init__.py
│   ├── extractor.py
│   ├── file_handler.py
│   ├── llm_analyzer.py
│   ├── processor.py
│   └── search.py
├── .cache
│   └── llm_analysis
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Module Responsibilities

- `app.py`: Streamlit UI, file upload, validation, progress updates, metrics, and download flow.
- `reader/file_handler.py`: Input file reading/validation and output CSV serialization.
- `reader/extractor.py`: URL fetch with retry and article text extraction fallback logic.
- `reader/search.py`: Keyword occurrence counting and paragraph-level match detection.
- `reader/processor.py`: End-to-end URL processing loop and dashboard metric aggregation.
- `reader/llm_analyzer.py`: LLM prompt/JSON parsing and 10-day content-hash cache lifecycle.

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

Configure LLM credentials (required for LLM analysis):

Option 1: Use `.env` file in project root (recommended).

1. Open `.env`
2. Set values:

```bash
# OpenAI option
OPENAI_API_KEY="your_openai_api_key"
OPENAI_MODEL="gpt-4.1-mini"
# OPENAI_BASE_URL="https://your-endpoint/v1"

# Gemini option (OpenAI-compatible endpoint)
GEMINI_API_KEY="your_gemini_api_key"
GEMINI_MODEL="gemini-2.0-flash"
# GEMINI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai"
```

Option 2: Export variables in terminal.

```bash
export OPENAI_API_KEY="your_api_key"
export OPENAI_MODEL="gpt-4.1-mini"
# optional, only if using an OpenAI-compatible endpoint
# export OPENAI_BASE_URL="https://your-endpoint/v1"

# OR Gemini variables
export GEMINI_API_KEY="your_gemini_api_key"
export GEMINI_MODEL="gemini-2.0-flash"
```

### Step-By-Step (macOS)

Run these commands from the project folder:

```bash
cd "/Users/ekprit/Work/Projects/3RD System - Media Intelligence"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Which file to run:

- The main application entry file is `app.py`.
- You run it with `streamlit run app.py`.
- Browser opens to the Streamlit interface (usually `http://localhost:8501`).

How to use the app after it starts:

1. Upload a `.csv` or `.xlsx` file.
2. Confirm it contains a `URL` column.
3. Enter your search term.
4. Click `Start Processing`.
5. Wait for progress and live status updates.
6. Review summary metrics and table.
7. Click `Download Results`.

### Fast Run with Makefile

If you prefer one-command steps:

```bash
cd "/Users/ekprit/Work/Projects/3RD System - Media Intelligence"
make venv
make install
make run
```

Set the API key first in the same terminal session before `make run`.

If you use `.env`, no extra export command is required.

Available Makefile targets:

- `make help`
- `make venv`
- `make install`
- `make run`
- `make clean`

## Run

```bash
streamlit run app.py
```

## Input Requirements

- File format: `.csv` or `.xlsx`
- Must include a column exactly named `URL`
- URLs should be publicly accessible article links
- Optional `Sentiment` column can be provided for sentiment comparison

## Processing Behavior

- Every URL is attempted and retried once if the first request fails.
- If both attempts fail, that row is marked `Failed` with the error message.
- If extraction returns no readable content, that row is marked `Failed`.
- Remaining URLs continue processing regardless of failures.
- Pages blocked by email/signup continue gates are marked as `Failed` with error `Access Gate: Email Required`.
- Duplicate detection uses up to three user-selected input columns and flags rows as duplicate (`Yes`/`No`).
- LLM analysis runs only for rows that reached successful extraction.
- If LLM analysis fails, scraping/search results remain intact and output columns are set to `LLM Failed`.
- When uploaded `Sentiment` differs from generated sentiment, `Sentiment Comparison` is `Mismatch`.
- In exported `.xlsx`, mismatch cells in `Sentiment Comparison` are highlighted yellow.
- LLM cache key is based on SHA-256 hash of extracted article text (not URL).
- Cached entries expire after 10 days and are cleaned automatically.

## Extensibility Path

This prototype is intentionally modular so it can be extended with:

- Browser automation (Playwright/Selenium) for dynamic sites
- AI-based entity extraction and article classification
- Additional content quality checks and source-level analytics
- Alternate export formats and database persistence
