"""Candidate display name and headline from resume text."""

from app.services.candidate_service import display_name, headline


def test_name_and_headline_from_the_top_lines() -> None:
    text = (
        "Ruby Castellanos\nSenior Backend Engineer · 8 years\nSydney · a@b.com · +61 745 187 1960\n"
    )
    assert display_name(text, "cv.pdf") == "Ruby Castellanos"
    assert headline(text) == "Senior Backend Engineer · 8 years"


def test_two_column_wraps_are_rejoined() -> None:
    text = (
        "Name: Amara\nPetrov\nTalent Acquisition Specialist with 4\nyears of experience\nCONTACT\n"
    )
    assert display_name(text, "cv.pdf") == "Amara Petrov"
    assert headline(text) == "Talent Acquisition Specialist with 4 years of experience"


def test_no_name_falls_back_to_the_file_name_and_no_headline() -> None:
    text = "CURRICULUM VITAE\nExperience\n..."
    assert display_name(text, "jane_doe-resume.pdf") == "jane doe resume"
    assert headline(text) is None


def test_contact_line_is_not_a_headline() -> None:
    assert headline("Priya Sharma\npriya@example.com · +44 7700 900123\n") is None


# ---------------------------------------------------------------- provisional job titles

from app.services.job_service import provisional_title  # noqa: E402


def test_provisional_title_skips_job_board_noise() -> None:
    text = (
        "Promoted · Easy Apply · 213 applicants · Posted 3 days ago\nApply now   Save   Share\n"
        "Salary: $95K/yr - $140K/yr · Full-time\n\nDevOps Engineer\nVantage Mobility · London\n"
    )
    assert provisional_title(text, "pasted.txt", pasted=True) == "DevOps Engineer"


def test_provisional_title_cuts_a_run_on_paragraph() -> None:
    text = "Talent Acquisition Specialist at Tidewater Bank (Sydney, hybrid). We are a team of 600."
    assert provisional_title(text, "pasted.txt", pasted=True) == "Talent Acquisition Specialist"


def test_provisional_title_for_a_pdf_is_its_file_name() -> None:
    assert provisional_title("x", "Senior SRE.pdf", pasted=False) == "Senior SRE"
