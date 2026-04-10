# tax-agent

AI agent for Korean personal income tax — document parsing, tax calculation, regulation lookup, and deduction strategy in one CLI.

## What It Does

```
Tax documents → parse → calculate → lookup regulations → suggest deductions
```

Given income documents (PDF, image, or manual input), the agent:
1. Parses and extracts income/expense figures
2. Calculates tax liability using the 2024 소득세법 bracket table
3. Looks up relevant regulations via the 법제처 Open API
4. Proposes applicable deductions and saves the session

## Tech Stack

| Layer | Stack |
|---|---|
| CLI runtime | Python 3.12, `rich` |
| Document parsing | `pdfplumber`, `pytesseract`, `Pillow` |
| Tax engine | Custom Python — 2024 소득세법 §55 brackets hardcoded |
| Regulation lookup | 법제처 Open API (조문 원문 직접 조회) |
| Storage | SQLite (session history) |
| Package manager | `uv` |

## Quick Start

```bash
uv run python main.py
```

## Project Structure

```
main.py               CLI entry point
tax_calculator.py     2024 income tax bracket engine
document_parser.py    PDF/image → structured income data
legal_search.py       법제처 API wrapper
strategy_engine.py    Deduction strategy suggestions
tax_store.py          SQLite session storage
eval_scenarios.py     Test scenarios for bracket validation
data/                 Extracted regulation text (법제처 API snapshots)
```

## Status

Phase 1 (CLI prototype) — in progress.  
Phase 2 planned: FastAPI backend + Next.js web UI, PostgreSQL, PDF upload endpoint.

## Goal

- Tax document → strategy suggestion in under 10 minutes
- Suggested deductions match certified tax accountant review at 80%+
- Zero regulation citation errors (법제처 API as source of truth)
