import os
import secrets
from datetime import datetime
from functools import wraps
from typing import Any
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

from utils.database import (
    create_application,
    create_candidate,
    create_job_description,
    create_resume,
    create_user,
    delete_job_description,
    delete_resume,
    get_candidate_by_id,
    get_candidate_by_user_id,
    get_connection,
    get_evaluations_for_resume,
    get_job_description,
    get_latest_evaluation,
    get_resume,
    get_ranking_rows,
    get_user_by_id,
    init_db,
    list_applications_for_job,
    list_candidates,
    list_hr_users,
    list_job_descriptions,
    list_resumes,
    save_evaluation,
    update_candidate,
    update_job_description,
    verify_user,
)
from utils.parser import extract_text
from utils.gemini_ai import generate_resume_analysis
from utils.ats import calculate_dashboard_metrics
from utils.reports import export_csv_report, export_pdf_report

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

init_db()


@app.context_processor
def inject_globals() -> dict[str, Any]:
    user = None
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
    return {"current_user": user, "csrf_token": session.get("csrf_token")}


def require_login(role: str | None = None) -> Any:
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            user = get_user_by_id(session["user_id"])
            if role and user["role"] != role:
                flash("You do not have access to this page.", "danger")
                return redirect(url_for("home"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.before_request
def ensure_csrf_token() -> None:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)


@app.route("/")
def home() -> str:
    return render_template("index.html")


@app.route("/about")
def about() -> str:
    return render_template("about.html")


@app.route("/contact")
def contact() -> str:
    return render_template("contact.html")


@app.route("/jobs")
def jobs() -> str:
    jobs = list_job_descriptions()
    return render_template("jobs.html", jobs=jobs)


@app.route("/jobs/apply/<int:job_id>", methods=["POST"])
@require_login("candidate")
def apply_job(job_id: int) -> Any:
    candidate = get_candidate_by_user_id(session["user_id"])
    if not candidate:
        flash("Candidate profile not found.", "danger")
        return redirect(url_for("jobs"))

    job = get_job_description(job_id)
    if not job:
        flash("Job posting not found.", "warning")
        return redirect(url_for("jobs"))

    application = create_application(candidate["id"], job_id)
    if application == 0:
        flash("You have already applied to this role.", "info")
    else:
        flash("Application submitted successfully.", "success")
    return redirect(url_for("jobs"))


@app.route("/login", methods=["GET", "POST"])
def login() -> str | Any:
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "warning")
            return redirect(url_for("login"))
        user = verify_user(email, password)
        if user:
            session["user_id"] = user["id"]
            role = user["role"]
            if role == "admin":
                return redirect(url_for("admin_dashboard"))
            if role == "hr":
                return redirect(url_for("hr_dashboard"))
            return redirect(url_for("candidate_dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register() -> str | Any:
    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("register"))

        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        skills = request.form.get("skills", "").strip()
        education = request.form.get("education", "").strip()
        experience = request.form.get("experience", "").strip()
        password = request.form.get("password", "")
        resume_file = request.files.get("resume")

        if not all([full_name, email, phone, skills, education, experience, password]):
            flash("All fields are required.", "warning")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "warning")
            return redirect(url_for("register"))

        if resume_file and resume_file.filename:
            filename = secure_filename(resume_file.filename)
            ext = os.path.splitext(filename)[1].lower()
            if ext not in {".pdf", ".docx"}:
                flash("Only PDF and DOCX resume files are supported.", "danger")
                return redirect(url_for("register"))
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            resume_file.save(save_path)
        else:
            save_path = ""
            filename = ""
            ext = ""

        try:
            user_id = create_user(full_name.lower().replace(" ", ""), email, password, "candidate")
            candidate_id = create_candidate(user_id, full_name, email, phone, skills, education, experience)
            if resume_file and resume_file.filename:
                extracted_text = extract_text(save_path, ext[1:].lower())
                create_resume(candidate_id, filename, save_path, ext[1:].lower(), extracted_text)
            flash("Registration successful. You can now log in.", "success")
            return redirect(url_for("login"))
        except Exception as exc:
            flash(f"Registration failed: {exc}", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/logout")
def logout() -> Any:
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/admin/dashboard")
@require_login("admin")
def admin_dashboard() -> str:
    candidates = list_candidates()
    jobs = list_job_descriptions()
    resumes = list_resumes()
    metrics = calculate_dashboard_metrics(candidates, jobs, resumes)
    return render_template("admin_dashboard.html", candidates=candidates, jobs=jobs, resumes=resumes, metrics=metrics)


@app.route("/hr/dashboard")
@require_login("hr")
def hr_dashboard() -> str:
    jobs = list_job_descriptions()
    candidates = list_candidates()
    resumes = list_resumes()
    metrics = calculate_dashboard_metrics(candidates, jobs, resumes)
    return render_template("hr_dashboard.html", jobs=jobs, candidates=candidates, resumes=resumes, metrics=metrics)


@app.route("/hr/job/<int:job_id>/applicants")
@require_login("hr")
def hr_job_applicants(job_id: int) -> str:
    job = get_job_description(job_id)
    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for("hr_dashboard"))

    applications = list_applications_for_job(job_id)
    return render_template("hr_applicants.html", job=job, applications=applications)


@app.route("/candidate/dashboard")
@require_login("candidate")
def candidate_dashboard() -> str:
    candidate = get_candidate_by_user_id(session["user_id"])
    resumes = []
    evaluations = []
    if candidate:
        conn = get_connection()
        candidate_resumes = conn.execute("SELECT * FROM resumes WHERE candidate_id = ? ORDER BY uploaded_at DESC", (candidate["id"],)).fetchall()
        conn.close()
        resumes = [dict(item) for item in candidate_resumes]
        if resumes:
            evaluations = get_evaluations_for_resume(resumes[0]["id"])
    return render_template("candidate_dashboard.html", candidate=candidate, resumes=resumes, evaluations=evaluations)


@app.route("/upload/resume", methods=["GET", "POST"])
@require_login("candidate")
def upload_resume() -> str | Any:
    candidate = get_candidate_by_user_id(session["user_id"])
    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("upload_resume"))
        uploaded_file = request.files.get("resume")
        if not uploaded_file or not uploaded_file.filename:
            flash("Please upload a valid resume file.", "warning")
            return redirect(url_for("upload_resume"))
        filename = secure_filename(uploaded_file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in {".pdf", ".docx"}:
            flash("Unsupported file type.", "danger")
            return redirect(url_for("upload_resume"))
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        uploaded_file.save(save_path)
        extracted_text = extract_text(save_path, ext[1:].lower())
        resume_id = create_resume(candidate["id"], filename, save_path, ext[1:].lower(), extracted_text)
        for job in list_job_descriptions():
            analysis = generate_resume_analysis(job["full_description"], extracted_text)
            save_evaluation(
                resume_id,
                job["id"],
                analysis["ats_score"],
                analysis["match_score"],
                analysis["recommendation"],
                analysis["strengths"],
                analysis["matched_skills"],
                analysis["missing_skills"],
                analysis["suggestions"],
                analysis["feedback"],
            )
        flash("Resume uploaded successfully.", "success")
        return redirect(url_for("candidate_dashboard"))
    return render_template("upload_resume.html", candidate=candidate)


@app.route("/upload/job", methods=["GET", "POST"])
@require_login("hr")
def upload_job() -> str | Any:
    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("upload_job"))
        job_title = request.form.get("job_title", "").strip()
        company_name = request.form.get("company_name", "").strip()
        required_skills = request.form.get("required_skills", "").strip()
        required_experience = request.form.get("required_experience", "").strip()
        full_description = request.form.get("full_description", "").strip()
        if not all([job_title, company_name, required_skills, required_experience, full_description]):
            flash("All job description fields are required.", "warning")
            return redirect(url_for("upload_job"))
        create_job_description(session["user_id"], job_title, company_name, required_skills, required_experience, full_description)
        flash("Job description created.", "success")
        return redirect(url_for("hr_dashboard"))
    return render_template("upload_job.html")


@app.route("/admin/candidates")
@require_login("admin")
def admin_candidates() -> str:
    search = request.args.get("search", "").strip()
    recommendation = request.args.get("recommendation", "")
    candidates = list_candidates()
    if search:
        search_lower = search.lower()
        candidates = [candidate for candidate in candidates if search_lower in candidate["full_name"].lower() or search_lower in candidate["email"].lower() or search_lower in candidate["skills"].lower()]
    if recommendation:
        candidates = [candidate for candidate in candidates if recommendation.lower() in candidate.get("skills", "").lower()]
    return render_template("candidate_list.html", candidates=candidates, search=search, recommendation=recommendation)


@app.route("/admin/hr-users", methods=["GET", "POST"])
@require_login("admin")
def admin_hr_users() -> str | Any:
    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("admin_hr_users"))
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not all([username, email, password]):
            flash("All HR user fields are required.", "warning")
            return redirect(url_for("admin_hr_users"))
        create_user(username, email, password, "hr")
        flash("HR user created.", "success")
        return redirect(url_for("admin_hr_users"))
    users = list_hr_users()
    return render_template("hr_users.html", users=users)


@app.route("/admin/job-descriptions")
@require_login("admin")
def admin_job_descriptions() -> str:
    jobs = list_job_descriptions()
    return render_template("job_descriptions.html", jobs=jobs)


@app.route("/admin/resumes")
@require_login("admin")
def admin_resumes() -> str:
    resumes = list_resumes()
    return render_template("admin_resumes.html", resumes=resumes)


@app.route("/admin/delete-resume/<int:resume_id>", methods=["POST"])
@require_login("admin")
def delete_resume_route(resume_id: int) -> Any:
    if request.form.get("csrf_token") != session.get("csrf_token"):
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("admin_resumes"))
    resume = get_resume(resume_id)
    if resume and os.path.exists(resume["file_path"]):
        os.remove(resume["file_path"])
    delete_resume(resume_id)
    flash("Resume deleted.", "success")
    return redirect(url_for("admin_resumes"))


@app.route("/admin/edit-candidate/<int:candidate_id>", methods=["GET", "POST"])
@require_login("admin")
def edit_candidate(candidate_id: int) -> str | Any:
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        flash("Candidate not found.", "danger")
        return redirect(url_for("admin_candidates"))
    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("edit_candidate", candidate_id=candidate_id))
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        skills = request.form.get("skills", "").strip()
        education = request.form.get("education", "").strip()
        experience = request.form.get("experience", "").strip()
        update_candidate(candidate_id, full_name, email, phone, skills, education, experience)
        flash("Candidate updated.", "success")
        return redirect(url_for("admin_candidates"))
    return render_template("edit_candidate.html", candidate=candidate)


@app.route("/admin/delete-job/<int:job_id>", methods=["POST"])
@require_login("admin")
def delete_job_route(job_id: int) -> Any:
    if request.form.get("csrf_token") != session.get("csrf_token"):
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("admin_job_descriptions"))
    delete_job_description(job_id)
    flash("Job description deleted.", "success")
    return redirect(url_for("admin_job_descriptions"))


@app.route("/hr/ranking")
@require_login("hr")
def ranking() -> str:
    ranking_rows = get_ranking_rows()
    return render_template("ranking.html", ranking_rows=ranking_rows)


@app.route("/analytics")
@require_login("hr")
def analytics() -> str:
    candidates = list_candidates()
    jobs = list_job_descriptions()
    resumes = list_resumes()
    metrics = calculate_dashboard_metrics(candidates, jobs, resumes)
    return render_template("analytics.html", metrics=metrics, candidates=candidates, jobs=jobs, resumes=resumes)


@app.route("/reports")
@require_login("hr")
def reports() -> str:
    resumes = list_resumes()
    return render_template("reports.html", resumes=resumes)


@app.route("/export/csv")
@require_login("hr")
def export_csv() -> Any:
    csv_content = export_csv_report(list_resumes())
    return send_file(csv_content, download_name="resume_report.csv", as_attachment=True, mimetype="text/csv")


@app.route("/export/pdf")
@require_login("hr")
def export_pdf() -> Any:
    pdf_bytes = export_pdf_report(list_resumes())
    return send_file(pdf_bytes, download_name="resume_report.pdf", as_attachment=True, mimetype="application/pdf")


@app.route("/candidate/profile", methods=["GET", "POST"])
@require_login("candidate")
def profile() -> str | Any:
    candidate = get_candidate_by_user_id(session["user_id"])
    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("profile"))
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        skills = request.form.get("skills", "").strip()
        education = request.form.get("education", "").strip()
        experience = request.form.get("experience", "").strip()
        update_candidate(candidate["id"], full_name, email, phone, skills, education, experience)
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", candidate=candidate)


@app.route("/candidate/settings")
@require_login("candidate")
def settings() -> str:
    candidate = get_candidate_by_user_id(session["user_id"])
    return render_template("settings.html", candidate=candidate)


@app.route("/candidate/application-status")
@require_login("candidate")
def application_status() -> str:
    candidate = get_candidate_by_user_id(session["user_id"])
    resumes = []
    evaluations = []
    if candidate:
        conn = get_connection()
        rows = conn.execute("SELECT resumes.*, candidates.full_name FROM resumes JOIN candidates ON candidates.id = resumes.candidate_id WHERE candidate_id = ? ORDER BY uploaded_at DESC", (candidate["id"],)).fetchall()
        conn.close()
        resumes = [dict(row) for row in rows]
        if resumes:
            evaluations = get_evaluations_for_resume(resumes[0]["id"])
    return render_template("application_status.html", candidate=candidate, resumes=resumes, evaluations=evaluations)


@app.errorhandler(404)
def page_not_found(_error: Any) -> str:
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
