import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','hr','candidate')),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            skills TEXT NOT NULL,
            education TEXT NOT NULL,
            experience TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS job_descriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hr_user_id INTEGER NOT NULL,
            job_title TEXT NOT NULL,
            company_name TEXT NOT NULL,
            required_skills TEXT NOT NULL,
            required_experience TEXT NOT NULL,
            full_description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (hr_user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            extracted_text TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            ats_score REAL NOT NULL,
            match_score REAL NOT NULL,
            recommendation TEXT NOT NULL,
            strengths TEXT NOT NULL,
            matched_skills TEXT NOT NULL,
            missing_skills TEXT NOT NULL,
            suggestions TEXT NOT NULL,
            feedback TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES job_descriptions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            applied_at TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES job_descriptions(id) ON DELETE CASCADE,
            UNIQUE(candidate_id, job_id)
        );
        """
    )
    conn.commit()
    conn.close()

    ensure_default_admin()
    ensure_default_hr()


def ensure_default_admin() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    if cursor.fetchone():
        conn.close()
        return

    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            "admin",
            "admin@company.com",
            generate_password_hash("admin123"),
            "admin",
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def ensure_default_hr() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE role = 'hr' LIMIT 1")
    if cursor.fetchone():
        conn.close()
        return

    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            "hr",
            "hr@company.com",
            generate_password_hash("hr123"),
            "hr",
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def create_user(username: str, email: str, password: str, role: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (username, email, generate_password_hash(password), role, datetime.utcnow().isoformat()),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def verify_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if not user:
        return None
    if check_password_hash(user["password_hash"], password):
        return dict(user)
    return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def create_candidate(user_id: int, full_name: str, email: str, phone: str, skills: str, education: str, experience: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO candidates (user_id, full_name, email, phone, skills, education, experience, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, full_name, email, phone, skills, education, experience, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
    )
    candidate_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return candidate_id


def update_candidate(candidate_id: int, full_name: str, email: str, phone: str, skills: str, education: str, experience: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE candidates SET full_name = ?, email = ?, phone = ?, skills = ?, education = ?, experience = ?, updated_at = ? WHERE id = ?",
        (full_name, email, phone, skills, education, experience, datetime.utcnow().isoformat(), candidate_id),
    )
    conn.commit()
    conn.close()


def get_candidate_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    candidate = conn.execute("SELECT * FROM candidates WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(candidate) if candidate else None


def get_candidate_by_id(candidate_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    candidate = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    conn.close()
    return dict(candidate) if candidate else None


def list_candidates() -> list[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM candidates ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_hr_users() -> list[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users WHERE role = 'hr' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_job_description(hr_user_id: int, job_title: str, company_name: str, required_skills: str, required_experience: str, full_description: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO job_descriptions (hr_user_id, job_title, company_name, required_skills, required_experience, full_description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (hr_user_id, job_title, company_name, required_skills, required_experience, full_description, datetime.utcnow().isoformat()),
    )
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id


def get_job_description(job_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM job_descriptions WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_job_descriptions() -> list[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM job_descriptions ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_applications_for_job(job_id: int) -> list[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT applications.id, applications.applied_at, candidates.full_name, candidates.email,
               candidates.phone, candidates.skills, candidates.education, candidates.experience
        FROM applications
        JOIN candidates ON candidates.id = applications.candidate_id
        WHERE applications.job_id = ?
        ORDER BY applications.applied_at DESC
        """,
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_application(candidate_id: int, job_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO applications (candidate_id, job_id, applied_at) VALUES (?, ?, ?)",
        (candidate_id, job_id, datetime.utcnow().isoformat()),
    )
    application_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return application_id


def get_application(candidate_id: int, job_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM applications WHERE candidate_id = ? AND job_id = ?", (candidate_id, job_id)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_applications_by_candidate(candidate_id: int) -> list[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM applications WHERE candidate_id = ? ORDER BY applied_at DESC", (candidate_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_job_description(job_id: int, job_title: str, company_name: str, required_skills: str, required_experience: str, full_description: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE job_descriptions SET job_title = ?, company_name = ?, required_skills = ?, required_experience = ?, full_description = ? WHERE id = ?",
        (job_title, company_name, required_skills, required_experience, full_description, job_id),
    )
    conn.commit()
    conn.close()


def delete_job_description(job_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM job_descriptions WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


def create_resume(candidate_id: int, filename: str, file_path: str, file_type: str, extracted_text: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO resumes (candidate_id, filename, file_path, file_type, extracted_text, uploaded_at) VALUES (?, ?, ?, ?, ?, ?)",
        (candidate_id, filename, file_path, file_type, extracted_text, datetime.utcnow().isoformat()),
    )
    resume_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return resume_id


def list_resumes() -> list[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT resumes.*, candidates.full_name FROM resumes JOIN candidates ON candidates.id = resumes.candidate_id ORDER BY resumes.uploaded_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_resume(resume_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_resume(resume_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
    conn.commit()
    conn.close()


def save_evaluation(resume_id: int, job_id: int, ats_score: float, match_score: float, recommendation: str, strengths: list[str], matched_skills: list[str], missing_skills: list[str], suggestions: str, feedback: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO evaluations (resume_id, job_id, ats_score, match_score, recommendation, strengths, matched_skills, missing_skills, suggestions, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            resume_id,
            job_id,
            ats_score,
            match_score,
            recommendation,
            ",".join(strengths),
            ",".join(matched_skills),
            ",".join(missing_skills),
            suggestions,
            feedback,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_evaluations_for_resume(resume_id: int) -> list[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM evaluations WHERE resume_id = ? ORDER BY created_at DESC", (resume_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_latest_evaluation(resume_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM evaluations WHERE resume_id = ? ORDER BY created_at DESC LIMIT 1", (resume_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_ranking_rows() -> list[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT candidates.full_name, evaluations.match_score, evaluations.ats_score, evaluations.recommendation, resumes.id AS resume_id
        FROM evaluations
        JOIN resumes ON resumes.id = evaluations.resume_id
        JOIN candidates ON candidates.id = resumes.candidate_id
        ORDER BY evaluations.match_score DESC, evaluations.ats_score DESC
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
