# Evaluation set (Phase 4)

Golden JD/resume pairs used to check scoring quality and compare models.

```
eval/cases/<case_id>/
  jd.pdf
  resume.pdf
  expected.yaml
```

`expected.yaml`:

```yaml
description: "Senior backend JD vs strong Python candidate"
score_min: 70
score_max: 90
must_pass: [c_backend_python]     # criterion keys expected to be Full Pass (optional)
must_fail: []                     # criterion keys expected to Fail (optional)
reviewed_by: "recruiter name"
```

Aim for 15–30 cases: strong fits, clear mismatches, career switchers, keyword-stuffed resumes,
two-column layouts and at least one scanned PDF.

Do not commit real candidate data without consent; anonymise names, emails and phone numbers.
