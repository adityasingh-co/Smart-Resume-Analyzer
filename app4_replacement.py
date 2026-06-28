import base64
import datetime as dt
import io
import random
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import spacy
import streamlit as st
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from PIL import Image
from streamlit_tags import st_tags

from Courses import (
    android_course,
    ds_course,
    interview_videos,
    ios_course,
    resume_videos,
    uiux_course,
    web_course,
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "Uploaded_Resumes"
DB_PATH = BASE_DIR / "resume_data.db"

st.set_page_config(page_title="Smart Resume Analyzer", page_icon="📄", layout="wide")

SKILL_TAXONOMY = {
    "Data Science": {
        "keywords": {
            "python",
            "pandas",
            "numpy",
            "machine learning",
            "deep learning",
            "tensorflow",
            "pytorch",
            "sql",
            "power bi",
            "tableau",
            "statistics",
            "data analysis",
            "data science",
            "nlp",
            "scikit-learn",
            "opencv",
        },
        "recommended_skills": [
            "Machine Learning",
            "Data Analysis",
            "SQL",
            "Statistics",
            "Power BI",
            "Tableau",
        ],
        "courses": ds_course,
    },
    "Web Development": {
        "keywords": {
            "html",
            "css",
            "javascript",
            "typescript",
            "react",
            "node.js",
            "node",
            "express",
            "mongodb",
            "django",
            "flask",
            "bootstrap",
            "tailwind",
            "rest api",
            "web development",
        },
        "recommended_skills": [
            "React",
            "Node.js",
            "REST API Design",
            "MongoDB",
            "TypeScript",
            "Responsive Design",
        ],
        "courses": web_course,
    },
    "Android Development": {
        "keywords": {
            "java",
            "kotlin",
            "android",
            "android studio",
            "firebase",
            "xml",
            "jetpack compose",
            "room",
            "retrofit",
            "gradle",
        },
        "recommended_skills": [
            "Kotlin",
            "Android Studio",
            "Firebase",
            "Jetpack Compose",
            "REST Integration",
        ],
        "courses": android_course,
    },
    "iOS Development": {
        "keywords": {
            "swift",
            "swiftui",
            "ios",
            "xcode",
            "uikit",
            "core data",
            "cocoapods",
        },
        "recommended_skills": [
            "SwiftUI",
            "UIKit",
            "Xcode",
            "Core Data",
            "App Architecture",
        ],
        "courses": ios_course,
    },
    "UI/UX": {
        "keywords": {
            "figma",
            "adobe xd",
            "photoshop",
            "illustrator",
            "wireframing",
            "prototyping",
            "user research",
            "ui design",
            "ux design",
            "design systems",
        },
        "recommended_skills": [
            "Wireframing",
            "Prototyping",
            "User Research",
            "Design Systems",
            "Usability Testing",
        ],
        "courses": uiux_course,
    },
}

ALL_SKILLS = sorted(
    {
        skill
        for field_data in SKILL_TAXONOMY.values()
        for skill in (field_data["keywords"] | set(field_data["recommended_skills"]))
    }
)

NAME_STOP_WORDS = {
    "resume",
    "curriculum",
    "vitae",
    "profile",
    "developer",
    "engineer",
    "analyst",
    "student",
    "intern",
    "contact",
    "summary",
    "objective",
    "education",
    "experience",
    "projects",
    "skills",
    "certifications",
}

EDUCATION_KEYWORDS = (
    "b.tech",
    "b.e",
    "bachelor",
    "master",
    "m.tech",
    "mca",
    "bca",
    "mba",
    "phd",
    "diploma",
    "college",
    "university",
    "school",
)

EXPERIENCE_KEYWORDS = (
    "intern",
    "engineer",
    "developer",
    "analyst",
    "consultant",
    "manager",
    "lead",
    "specialist",
)

EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_PATTERN = re.compile(
    r"(?:(?:\+?\d{1,3}[\s\-().]*)?(?:\d[\s\-().]*){10,14})"
)

NLP = spacy.blank("en")
SKILL_MATCHER = spacy.matcher.PhraseMatcher(NLP.vocab, attr="LOWER")
SKILL_MATCHER.add("SKILLS", [NLP.make_doc(skill) for skill in ALL_SKILLS])


def get_connection():
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


CONNECTION = get_connection()


def create_user_table():
    CONNECTION.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            resume_score REAL,
            timestamp TEXT,
            no_of_pages TEXT,
            predicted_field TEXT,
            user_level TEXT,
            skills TEXT,
            recommended_skills TEXT,
            recommended_courses TEXT
        )
        """
    )
    CONNECTION.commit()


def get_table_download_link(dataframe, filename, text):
    csv = dataframe.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'


def pdf_reader(file_path):
    resource_manager = PDFResourceManager()
    fake_file_handle = io.StringIO()
    converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
    page_interpreter = PDFPageInterpreter(resource_manager, converter)

    with open(file_path, "rb") as pdf_file:
        for page in PDFPage.get_pages(pdf_file, caching=True, check_extractable=True):
            page_interpreter.process_page(page)

    text = fake_file_handle.getvalue()
    converter.close()
    fake_file_handle.close()
    return text


def count_pdf_pages(file_path):
    with open(file_path, "rb") as pdf_file:
        return sum(1 for _ in PDFPage.get_pages(pdf_file, caching=True, check_extractable=True))


def normalize_whitespace(value):
    return re.sub(r"\s+", " ", value or "").strip()


def extract_email(text):
    match = EMAIL_PATTERN.search(text or "")
    return match.group(0) if match else None


def extract_phone_number(text):
    for match in PHONE_PATTERN.findall(text or ""):
        digits = re.sub(r"\D", "", match)
        if 10 <= len(digits) <= 13:
            if len(digits) > 10 and digits.startswith("91"):
                digits = digits[-10:]
            return digits
    return None


def is_probable_name(line):
    if not line:
        return False
    if any(char.isdigit() for char in line):
        return False
    if "@" in line or len(line) > 60:
        return False
    words = [part for part in re.split(r"\s+", line) if part]
    if not 2 <= len(words) <= 4:
        return False
    lowered = {re.sub(r"[^a-z]", "", word.lower()) for word in words}
    lowered.discard("")
    if lowered & NAME_STOP_WORDS:
        return False
    return all(re.fullmatch(r"[A-Za-z][A-Za-z.\-']*", word) for word in words)


def extract_name(text):
    lines = [normalize_whitespace(line) for line in (text or "").splitlines()]
    candidate_lines = [line for line in lines[:12] if line]
    for line in candidate_lines:
        if is_probable_name(line):
            return line.title()
    return None


def extract_education(lines):
    education = []
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in EDUCATION_KEYWORDS):
            education.append(line)
    return education[:5]


def extract_experience(lines):
    experience = []
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in EXPERIENCE_KEYWORDS):
            experience.append(line)
    return experience[:8]


def extract_skills(text):
    doc = NLP(text or "")
    matches = SKILL_MATCHER(doc)
    found = {doc[start:end].text.strip() for _, start, end in matches}

    normalized = set()
    for skill in found:
        lowered = skill.lower()
        for canonical_skill in ALL_SKILLS:
            if lowered == canonical_skill.lower():
                normalized.add(canonical_skill.title() if canonical_skill.islower() else canonical_skill)
                break

    return sorted(normalized, key=str.lower)


def parse_resume(file_path):
    text = pdf_reader(file_path)
    lines = [normalize_whitespace(line) for line in text.splitlines() if normalize_whitespace(line)]
    return {
        "name": extract_name(text),
        "email": extract_email(text),
        "mobile_number": extract_phone_number(text),
        "education": extract_education(lines),
        "experience": extract_experience(lines),
        "skills": extract_skills(text),
        "raw_text": text,
        "no_of_pages": count_pdf_pages(file_path),
    }


def analyze_resume(uploaded_file):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOAD_DIR / uploaded_file.name

    with open(save_path, "wb") as output_file:
        output_file.write(uploaded_file.getbuffer())

    show_pdf(save_path)
    return parse_resume(save_path), str(save_path)


def show_pdf(file_path):
    with open(file_path, "rb") as pdf_file:
        base64_pdf = base64.b64encode(pdf_file.read()).decode("utf-8")
    pdf_display = (
        f'<iframe src="data:application/pdf;base64,{base64_pdf}" '
        'width="100%" height="700" type="application/pdf"></iframe>'
    )
    st.markdown(pdf_display, unsafe_allow_html=True)


def analyze_skills(resume_data):
    extracted_skills = {skill.lower() for skill in resume_data.get("skills", [])}
    predicted_field = "General"
    recommended_skills = ["Communication", "Problem Solving", "Project Documentation"]
    fallback_courses = web_course + ds_course
    rec_course = random.sample(fallback_courses, k=min(4, len(fallback_courses)))
    best_score = 0

    for field_name, field_data in SKILL_TAXONOMY.items():
        overlap = len(extracted_skills & {skill.lower() for skill in field_data["keywords"]})
        if overlap > best_score:
            best_score = overlap
            predicted_field = field_name
            recommended_skills = field_data["recommended_skills"]
            rec_course = field_data["courses"]

    return recommended_skills, predicted_field, rec_course


def calculate_resume_score(resume_data, recommended_skills):
    score = 0

    if resume_data.get("name"):
        score += 15
    if resume_data.get("email"):
        score += 15
    if resume_data.get("mobile_number"):
        score += 10
    if resume_data.get("education"):
        score += 15
    if resume_data.get("experience"):
        score += 15
    if resume_data.get("skills"):
        score += 15

    extracted_skills = {skill.lower() for skill in resume_data.get("skills", [])}
    score += sum(3 for skill in recommended_skills if skill.lower() in extracted_skills)

    no_of_pages = resume_data.get("no_of_pages") or 1
    if no_of_pages == 1:
        score += 12
    elif no_of_pages == 2:
        score += 8
    elif no_of_pages > 3:
        score -= 5

    return max(0, min(100, score))


def determine_candidate_level(resume_data):
    experience_entries = resume_data.get("experience") or []
    if not experience_entries:
        return "Beginner"
    if len(experience_entries) <= 3:
        return "Intermediate"
    return "Expert"


def insert_data(
    name,
    email,
    resume_score,
    timestamp,
    no_of_pages,
    predicted_field,
    candidate_level,
    skills,
    recommended_skills,
    recommended_courses,
):
    CONNECTION.execute(
        """
        INSERT INTO resume_data (
            name,
            email,
            resume_score,
            timestamp,
            no_of_pages,
            predicted_field,
            user_level,
            skills,
            recommended_skills,
            recommended_courses
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            email,
            float(resume_score),
            timestamp,
            str(no_of_pages),
            predicted_field,
            candidate_level,
            ", ".join(skills),
            ", ".join(recommended_skills),
            ", ".join(recommended_courses),
        ),
    )
    CONNECTION.commit()


def fetch_all_resumes():
    rows = CONNECTION.execute(
        """
        SELECT
            id AS ID,
            name AS Name,
            email AS Email,
            resume_score AS "Resume Score",
            timestamp AS Timestamp,
            no_of_pages AS "Total Page",
            predicted_field AS "Predicted Field",
            user_level AS "User Level",
            skills AS Skills,
            recommended_skills AS "Recommended Skills",
            recommended_courses AS "Recommended Course"
        FROM resume_data
        ORDER BY id DESC
        """
    ).fetchall()
    return pd.DataFrame(rows)


def display_video_tips():
    st.header("Bonus Video for Resume Writing Tips")
    if resume_videos:
        st.video(random.choice(resume_videos))

    st.header("Bonus Video for Interview Tips")
    if interview_videos:
        st.video(random.choice(interview_videos))


def course_recommender(course_list):
    st.subheader("Courses and Certificate Recommendations")
    recommendation_count = st.slider("Choose Number of Course Recommendations:", 1, 10, 4)
    selected_courses = random.sample(course_list, k=min(recommendation_count, len(course_list)))
    recommended_names = []

    for index, (course_name, course_link) in enumerate(selected_courses, start=1):
        st.markdown(f"{index}. [{course_name}]({course_link})")
        recommended_names.append(course_name)

    return recommended_names


def show_resume_overview(resume_data):
    st.success(f"Hello {resume_data.get('name') or 'Candidate'}")
    st.text(f"Name: {resume_data.get('name') or 'N/A'}")
    st.text(f"Email: {resume_data.get('email') or 'N/A'}")
    st.text(f"Contact: {resume_data.get('mobile_number') or 'N/A'}")
    st.text(f"Resume pages: {resume_data.get('no_of_pages') or 'N/A'}")

    education = resume_data.get("education") or []
    if education:
        st.subheader("Education")
        for item in education:
            st.markdown(f"- {item}")


def handle_normal_user():
    pdf_file = st.file_uploader("Choose your Resume", type=["pdf"])
    if not pdf_file:
        return

    resume_data, _ = analyze_resume(pdf_file)
    show_resume_overview(resume_data)

    recommended_skills, predicted_field, rec_course = analyze_skills(resume_data)
    recommended_course_names = course_recommender(rec_course)
    resume_score = calculate_resume_score(resume_data, recommended_skills)
    candidate_level = determine_candidate_level(resume_data)
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.subheader("Skills Recommendation")
    st_tags(
        label="### Skills that you have",
        text="Extracted skills",
        value=resume_data.get("skills", []),
        key="skills_have",
    )
    st_tags(
        label="### Recommended skills for you",
        text="Recommended skills",
        value=recommended_skills,
        key="skills_recommended",
    )

    st.info(f"Predicted field: {predicted_field}")
    st.info(f"Candidate level: {candidate_level}")
    st.success(f"Your Resume Writing Score: {resume_score:.2f}")
    st.progress(resume_score / 100.0)

    insert_data(
        resume_data.get("name") or "N/A",
        resume_data.get("email") or "N/A",
        resume_score,
        timestamp,
        resume_data.get("no_of_pages") or "0",
        predicted_field,
        candidate_level,
        resume_data.get("skills", []),
        recommended_skills,
        recommended_course_names,
    )

    st.success("Your resume data has been stored successfully.")
    display_video_tips()


def handle_admin():
    st.success("Welcome to Admin Side")
    ad_user = st.text_input("Username")
    ad_password = st.text_input("Password", type="password")

    if not st.button("Login"):
        return

    if ad_user != "Amigoes" or ad_password != "Amigoes":
        st.error("Wrong ID and Password Provided")
        return

    st.success("Welcome Admin")
    dataframe = fetch_all_resumes()

    if dataframe.empty:
        st.warning("No data found in the database")
        return

    st.dataframe(dataframe, use_container_width=True)
    st.markdown(
        get_table_download_link(dataframe, "User_Data.csv", "Download Report"),
        unsafe_allow_html=True,
    )

    field_counts = dataframe["Predicted Field"].value_counts()
    st.plotly_chart(
        px.pie(names=field_counts.index, values=field_counts.values, title="Predicted Field"),
        use_container_width=True,
    )

    level_counts = dataframe["User Level"].value_counts()
    st.plotly_chart(
        px.pie(names=level_counts.index, values=level_counts.values, title="User Experience Level"),
        use_container_width=True,
    )


def render_logo():
    logo_candidates = [
        BASE_DIR / "Logo" / "SRA_Logo.jpg",
        BASE_DIR / "Logo" / "SRA_Logo.png",
    ]

    for logo_path in logo_candidates:
        if logo_path.exists():
            image = Image.open(logo_path).resize((220, 220))
            st.image(image)
            return


def run():
    create_user_table()
    st.title("Smart Resume Analyzer")
    render_logo()
    choice = st.sidebar.selectbox("Choose among the given options:", ["Normal User", "Admin"])

    if choice == "Normal User":
        handle_normal_user()
    else:
        handle_admin()


def in_streamlit_runtime():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__":
    if in_streamlit_runtime():
        run()
    else:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve())], check=False)
