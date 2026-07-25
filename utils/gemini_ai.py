import os
import requests
from typing import Dict, List

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def generate_resume_analysis(job_description: str, resume_text: str) -> Dict[str, object]:
    if not GEMINI_API_KEY:
        return fallback_analysis(job_description, resume_text)

    prompt = f"""
    You are an expert HR AI assistant. Analyze the resume against the job description.
    Return a JSON object with:
    - ats_score: integer 0-100
    - match_score: integer 0-100
    - recommendation: one of Selected, Shortlisted, Rejected
    - strengths: array of strings
    - matched_skills: array of strings
    - missing_skills: array of strings
    - suggestions: string
    - feedback: string

    Job Description:
    {job_description}

    Resume:
    {resume_text}
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    try:
        response = requests.post(f"{GEMINI_URL}?key={GEMINI_API_KEY}", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return parse_gemini_response(text)
    except Exception:
        return fallback_analysis(job_description, resume_text)


def parse_gemini_response(text: str) -> Dict[str, object]:
    import json

    data = json.loads(text)
    return {
        "ats_score": int(data.get("ats_score", 0)),
        "match_score": int(data.get("match_score", 0)),
        "recommendation": data.get("recommendation", "Rejected"),
        "strengths": data.get("strengths", []),
        "matched_skills": data.get("matched_skills", []),
        "missing_skills": data.get("missing_skills", []),
        "suggestions": data.get("suggestions", "Keep improving to increase compatibility."),
        "feedback": data.get("feedback", "Resume reviewed with AI assistance."),
    }


def fallback_analysis(job_description: str, resume_text: str) -> Dict[str, object]:
    job_lower = (job_description or "").lower()
    resume_lower = (resume_text or "").lower()
    required_skills = [item.strip().lower() for item in job_lower.split(",") if item.strip()]
    found_skills = [skill for skill in required_skills if skill in resume_lower]
    missing_skills = [skill for skill in required_skills if skill not in resume_lower]

    match_score = int(min(100, max(0, round((len(found_skills) / max(1, len(required_skills))) * 100)))) if required_skills else 0
    ats_score = min(100, max(0, int(round(match_score * 0.9 + (20 if len(found_skills) > 0 else 0)))))

    if match_score >= 85:
        recommendation = "Selected"
    elif match_score >= 70:
        recommendation = "Shortlisted"
    else:
        recommendation = "Rejected"

    strengths = found_skills[:5]
    suggestions = "Learn the missing skills and add measurable achievements to improve fit." if missing_skills else "Your profile is already well aligned with the role."
    feedback = "The resume shows a solid baseline. Strengthen the missing areas to improve the compatibility score."

    return {
        "ats_score": ats_score,
        "match_score": match_score,
        "recommendation": recommendation,
        "strengths": strengths,
        "matched_skills": found_skills,
        "missing_skills": missing_skills,
        "suggestions": suggestions,
        "feedback": feedback,
    }
