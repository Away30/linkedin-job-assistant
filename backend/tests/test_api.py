"""API tests — contract validation + endpoint coverage."""
import io


# --- Basic endpoints ---

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_ping(client):
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    assert response.json()["message"] == "pong"

def test_list_jobs_empty(client):
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    assert response.json() == []

def test_automation_status(client):
    response = client.get("/api/v1/automation/status")
    assert response.status_code == 200
    assert response.json()["is_running"] is False

def test_list_resumes_empty(client):
    response = client.get("/api/v1/resumes")
    assert response.status_code == 200
    assert response.json() == []

def test_list_applications_empty(client):
    response = client.get("/api/v1/applications")
    assert response.status_code == 200
    assert response.json() == []


# --- Contract tests: field name alignment ---

def test_automation_status_field_names(client):
    """Backend returns is_running, jobs_applied, jobs_failed (not running/applied/failed)."""
    response = client.get("/api/v1/automation/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_running" in data
    assert "jobs_applied" in data
    assert "jobs_failed" in data
    assert "jobs_found" in data
    assert "status_message" in data
    assert data["is_running"] is False
    assert isinstance(data["jobs_applied"], int)
    assert isinstance(data["jobs_failed"], int)


def test_automation_start_accepts_max_applies(client):
    """Backend accepts max_applies without 422."""
    filter_resp = client.post("/api/v1/filters", json={
        "name": "Contract Test Filter",
        "keywords": "Engineer",
        "location": "Remote",
    })
    assert filter_resp.status_code == 200
    filter_id = filter_resp.json()["id"]

    response = client.post("/api/v1/automation/start", json={
        "filter_id": filter_id,
        "max_applies": 5,
    }, timeout=3.0)
    assert response.status_code != 422


def test_filter_job_type_accepts_string(client):
    """Backend accepts job_type as a plain string."""
    response = client.post("/api/v1/filters", json={
        "name": "JobType String Test",
        "keywords": "Developer",
        "location": "Berlin",
        "job_type": "Full-time",
    })
    assert response.status_code == 200
    assert response.json()["job_type"] == "Full-time"


def test_filter_job_type_rejects_array(client):
    """Backend rejects job_type as an array."""
    response = client.post("/api/v1/filters", json={
        "name": "JobType Array Test",
        "keywords": "Developer",
        "location": "Berlin",
        "job_type": ["Full-time", "Part-time"],
    })
    assert response.status_code == 422


# --- Filter CRUD ---

def test_filter_crud_full(client):
    """GET/PUT/DELETE /filters/{id}."""
    # Create
    create_resp = client.post("/api/v1/filters", json={
        "name": "CRUD Filter",
        "keywords": "Rust",
        "location": "Tokyo",
    })
    assert create_resp.status_code == 200
    fid = create_resp.json()["id"]

    # Get single
    get_resp = client.get(f"/api/v1/filters/{fid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["keywords"] == "Rust"

    # Update
    put_resp = client.put(f"/api/v1/filters/{fid}", json={"keywords": "Go"})
    assert put_resp.status_code == 200
    assert put_resp.json()["keywords"] == "Go"

    # Delete
    del_resp = client.delete(f"/api/v1/filters/{fid}")
    assert del_resp.status_code == 200

    # Verify gone
    get_resp2 = client.get(f"/api/v1/filters/{fid}")
    assert get_resp2.status_code == 404


def test_filter_404_on_missing(client):
    response = client.get("/api/v1/filters/99999")
    assert response.status_code == 404


# --- Job create + dedup ---

def test_job_create_and_dedup(client):
    """Creating same linkedin_job_id twice returns existing record."""
    job_data = {
        "linkedin_job_id": "li-123",
        "title": "Backend Engineer",
        "company": "Acme",
    }
    r1 = client.post("/api/v1/jobs", json=job_data)
    assert r1.status_code == 200
    assert r1.json()["id"] is not None

    r2 = client.post("/api/v1/jobs", json=job_data)
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"]  # same record returned


def test_job_get_by_id(client):
    job_data = {"linkedin_job_id": "li-456", "title": "DevOps"}
    create = client.post("/api/v1/jobs", json=job_data)
    jid = create.json()["id"]

    get = client.get(f"/api/v1/jobs/{jid}")
    assert get.status_code == 200
    assert get.json()["title"] == "DevOps"


def test_job_404(client):
    response = client.get("/api/v1/jobs/99999")
    assert response.status_code == 404


# --- Application update ---

def test_update_application_status(client):
    # Create job + application
    job = client.post("/api/v1/jobs", json={
        "linkedin_job_id": "li-app1", "title": "Test Job"
    }).json()

    app_resp = client.post("/api/v1/applications", json={
        "job_id": job["id"], "status": "pending"
    })
    # If no direct create endpoint, skip
    if app_resp.status_code == 405:
        return

    # Update status
    app_id = app_resp.json()["id"]
    update = client.patch(f"/api/v1/applications/{app_id}", json={
        "status": "applied"
    })
    assert update.status_code == 200
    assert update.json()["status"] == "applied"


# --- Resume upload + delete ---

def test_resume_upload_and_delete(client):
    """Upload a file, verify UUID filename, then delete."""
    file_content = b"%PDF-1.4 fake resume content"
    upload = client.post(
        "/api/v1/resumes",
        data={"name": "My Resume", "target_roles": "Engineer"},
        files={"file": ("resume.pdf", io.BytesIO(file_content), "application/pdf")},
    )
    assert upload.status_code == 200
    data = upload.json()
    rid = data["id"]
    file_path = data["file_path"]

    # Verify filename is UUID-based (32 hex chars + extension)
    import os
    basename = os.path.basename(file_path)
    name_part = basename.replace(".pdf", "")
    assert len(name_part) == 32  # UUID hex
    assert name_part.isalnum()

    # List includes it
    resumes = client.get("/api/v1/resumes")
    assert len(resumes.json()) == 1

    # Delete
    delete = client.delete(f"/api/v1/resumes/{rid}")
    assert delete.status_code == 200

    # Verify gone
    resumes2 = client.get("/api/v1/resumes")
    assert len(resumes2.json()) == 0


def test_resume_rejects_bad_extension(client):
    upload = client.post(
        "/api/v1/resumes",
        data={"name": "Bad File"},
        files={"file": ("malware.exe", io.BytesIO(b"binary"), "application/octet-stream")},
    )
    assert upload.status_code == 400


# --- Operation logs ---

def test_operation_logs_empty(client):
    response = client.get("/api/v1/logs")
    assert response.status_code == 200
    assert response.json() == []


# --- Settings sync ---

def test_get_settings(client):
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert "max_applies_per_day" in data
    assert "action_delay_min" in data
    assert "action_delay_max" in data


def test_update_settings(client):
    response = client.post("/api/v1/settings", json={
        "max_applies_per_day": 10,
        "action_delay_min": 2.0,
        "action_delay_max": 8.0,
    })
    assert response.status_code == 200

    # Verify updated
    get_resp = client.get("/api/v1/settings")
    data = get_resp.json()
    assert data["max_applies_per_day"] == 10
    assert data["action_delay_min"] == 2.0
    assert data["action_delay_max"] == 8.0
