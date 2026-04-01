"""SQLite 데이터 영속성 모듈

테이블: users, tax_documents, tax_strategies, tax_calculations
DB 파일: tax_data.db (프로젝트 루트)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "tax_data.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """테이블 초기화 (없으면 생성)."""
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id        INTEGER PRIMARY KEY,
                name      TEXT,
                tax_year  INTEGER,
                income_type TEXT,
                flags     TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS tax_documents (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                doc_type   TEXT,
                raw_text   TEXT,
                parsed_data TEXT,
                tax_year   INTEGER,
                amount     REAL,
                uploaded_at TEXT
            );
            CREATE TABLE IF NOT EXISTS tax_strategies (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                tax_year   INTEGER,
                strategies TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS tax_calculations (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER,
                tax_year         INTEGER,
                gross_income     REAL,
                total_deductions REAL,
                taxable_income   REAL,
                result           TEXT,
                created_at       TEXT
            );
        """)


def save_user_profile(data):
    """사용자 프로필 저장 (id=1 고정, upsert)."""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO users (id, name, tax_year, income_type, flags, created_at)
            VALUES (1, :name, :tax_year, :income_type, :flags, :created_at)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                tax_year=excluded.tax_year,
                income_type=excluded.income_type,
                flags=excluded.flags
            """,
            {
                "name": data.get("name", ""),
                "tax_year": data.get("tax_year", datetime.now().year - 1),
                "income_type": json.dumps(data.get("income_type", []), ensure_ascii=False),
                "flags": json.dumps(data.get("flags", {}), ensure_ascii=False),
                "created_at": datetime.now().isoformat(),
            },
        )


def get_user_profile():
    """사용자 프로필 조회. 없으면 None 반환."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=1").fetchone()
        if row is None:
            return None
        d = dict(row)
        d["income_type"] = json.loads(d["income_type"] or "[]")
        d["flags"] = json.loads(d["flags"] or "{}")
        return d


def save_document(doc_data):
    """세무 자료 저장."""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO tax_documents
                (user_id, doc_type, raw_text, parsed_data, tax_year, amount, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_data.get("user_id", 1),
                doc_data.get("doc_type", "other"),
                doc_data.get("raw_text", ""),
                json.dumps(doc_data.get("parsed_data", {}), ensure_ascii=False),
                doc_data.get("tax_year", datetime.now().year - 1),
                doc_data.get("amount", 0),
                datetime.now().isoformat(),
            ),
        )


def list_documents():
    """저장된 세무 자료 목록 반환."""
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM tax_documents ORDER BY uploaded_at DESC").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["parsed_data"] = json.loads(d["parsed_data"] or "{}")
            result.append(d)
        return result


def save_calculation(calc_data):
    """세액 계산 결과 저장."""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO tax_calculations
                (user_id, tax_year, gross_income, total_deductions, taxable_income, result, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                calc_data.get("user_id", 1),
                calc_data.get("tax_year", datetime.now().year - 1),
                calc_data.get("gross_income", 0),
                calc_data.get("total_deductions", 0),
                calc_data.get("taxable_income", 0),
                json.dumps(calc_data.get("result", {}), ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )


def get_latest_calculation():
    """가장 최근 세액 계산 결과 반환."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM tax_calculations ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["result"] = json.loads(d["result"] or "{}")
        return d


def save_strategies(data):
    """절세 전략 저장."""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO tax_strategies (user_id, tax_year, strategies, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                data.get("user_id", 1),
                data.get("tax_year", datetime.now().year - 1),
                json.dumps(data.get("strategies", []), ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
