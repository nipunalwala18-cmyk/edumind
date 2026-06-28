"""
tests/test_document_viewer.py
------------------------------
Tests for the citation document viewer (backend/document_service.py + the
/api/documents/* endpoints).

Groups:
  TestRBACUnit        — pure RBAC matrix + traversal guard          (no server)
  TestAuthz           — endpoint authorization (public denied, etc.)
  TestServing         — streaming + highlighted HTML rendering
  TestAccessLevels    — role vs document access-level enforcement
  TestBackwardCompat  — existing endpoints still work

Run:  pytest tests/test_document_viewer.py -q
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend import document_service as ds


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    os.environ["TEST_DB"] = "1"
    from backend.database import Base, engine
    Base.metadata.create_all(bind=engine)
    from backend.app import app as _app
    return _app


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture(scope="session")
def seeded_db(app):
    from backend.database import SessionLocal, User
    from backend.auth import hash_password
    db = SessionLocal()
    seed = [
        ("admin_test", "Admin@123", "Admin"),
        ("student_test", "Student@123", "Student"),
        ("faculty_test", "Faculty@123", "Faculty"),
        ("public_user", "Public@123", "Public"),
    ]
    for u, p, r in seed:
        if not db.query(User).filter(User.username == u).first():
            db.add(User(username=u, hashed_password=hash_password(p), role=r))
    db.commit()
    db.close()


def _token(client, user, pw):
    return client.post("/api/auth/login", json={"username": user, "password": pw}).json()["access_token"]


@pytest.fixture
def tokens(client, seeded_db):
    return {
        "Admin":   _token(client, "admin_test", "Admin@123"),
        "Student": _token(client, "student_test", "Student@123"),
        "Faculty": _token(client, "faculty_test", "Faculty@123"),
        "Public":  _token(client, "public_user", "Public@123"),
    }


@pytest.fixture(scope="session")
def real_docx():
    """A real ingested .docx doc_id + resolved path from the ledger."""
    import ledger
    ledger.initialize_db()
    conn = ledger.get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT doc_id FROM documents "
        "WHERE doc_id IS NOT NULL AND source_file LIKE '%.docx' LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        pytest.skip("no ingested .docx documents in ledger")
    doc_id = row[0]
    ref = ds.load_document(doc_id)
    if ref is None:
        pytest.skip("document file not present on disk")
    return ref


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── RBAC unit tests ─────────────────────────────────────────────────────────

class TestRBACUnit:
    def test_public_role_cannot_open(self):
        assert ds.role_can_open("Public") is False
        assert ds.role_can_open("") is False
        assert ds.role_can_open(None) is False

    def test_authenticated_roles_can_open(self):
        for r in ("Student", "Faculty", "Admin"):
            assert ds.role_can_open(r) is True

    @pytest.mark.parametrize("role,level,expected", [
        ("Student", "Public", True),
        ("Student", "Student", True),
        ("Student", "Faculty", False),
        ("Student", "Admin", False),
        ("Faculty", "Faculty", True),
        ("Faculty", "Admin", False),
        ("Admin", "Confidential", True),
        ("Admin", "Faculty", True),
        ("Public", "Public", False),     # public role denied at access layer too
    ])
    def test_access_matrix(self, role, level, expected):
        assert ds.can_access(role, level) is expected

    def test_traversal_guard_rejects_escape(self):
        assert ds._safe_path("../../etc/passwd") is None
        assert ds._safe_path("..\\..\\windows\\system32\\config") is None
        assert ds._safe_path("") is None

    def test_detect_kind_by_extension_fallback(self, real_docx):
        assert real_docx.kind in ("docx", "doc", "pdf")


# ── Endpoint authorization ──────────────────────────────────────────────────

class TestAuthz:
    def test_view_requires_authentication(self, client, real_docx):
        r = client.get(f"/api/documents/{real_docx.doc_id}/view")
        assert r.status_code in (401, 403)

    def test_file_requires_authentication(self, client, real_docx):
        r = client.get(f"/api/documents/{real_docx.doc_id}/file")
        assert r.status_code in (401, 403)

    def test_public_user_denied_view(self, client, tokens, real_docx):
        r = client.get(f"/api/documents/{real_docx.doc_id}/view", headers=_hdr(tokens["Public"]))
        assert r.status_code == 403

    def test_public_user_denied_file(self, client, tokens, real_docx):
        r = client.get(f"/api/documents/{real_docx.doc_id}/file", headers=_hdr(tokens["Public"]))
        assert r.status_code == 403

    def test_public_user_denied_meta(self, client, tokens, real_docx):
        r = client.get(f"/api/documents/{real_docx.doc_id}/meta", headers=_hdr(tokens["Public"]))
        assert r.status_code == 403

    def test_unknown_doc_returns_404(self, client, tokens):
        r = client.get("/api/documents/deadbeefdeadbeef/view", headers=_hdr(tokens["Student"]))
        assert r.status_code == 404


# ── Serving + rendering ─────────────────────────────────────────────────────

class TestServing:
    def test_student_views_public_doc_highlighted(self, client, tokens, real_docx):
        r = client.get(
            f"/api/documents/{real_docx.doc_id}/view?chunk_index=0",
            headers=_hdr(tokens["Student"]),
        )
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "<mark>" in r.text                 # chunk highlighted
        assert real_docx.title[:20] in r.text or "doc-body" in r.text

    def test_view_does_not_leak_filesystem_path(self, client, tokens, real_docx):
        r = client.get(f"/api/documents/{real_docx.doc_id}/view", headers=_hdr(tokens["Student"]))
        assert r.status_code == 200
        assert str(real_docx.path) not in r.text
        assert "data\\staging" not in r.text and "data/staging" not in r.text

    def test_file_streams_bytes_inline(self, client, tokens, real_docx):
        r = client.get(f"/api/documents/{real_docx.doc_id}/file", headers=_hdr(tokens["Student"]))
        assert r.status_code == 200
        assert len(r.content) > 0
        assert "officedocument" in r.headers["content-type"] or "application/" in r.headers["content-type"]
        assert r.headers.get("content-disposition", "").startswith("inline")
        # path is never exposed in headers
        assert str(real_docx.path) not in str(r.headers)

    def test_meta_returns_safe_metadata(self, client, tokens, real_docx):
        r = client.get(f"/api/documents/{real_docx.doc_id}/meta", headers=_hdr(tokens["Faculty"]))
        assert r.status_code == 200
        data = r.json()
        assert data["doc_id"] == real_docx.doc_id
        assert data["kind"] in ("docx", "doc", "pdf")
        assert "access_level" in data and "title" in data
        assert "source_file" not in data and "path" not in data   # no path leak


# ── Access-level enforcement (role vs document) ─────────────────────────────

class TestAccessLevels:
    def _patch_level(self, monkeypatch, real_docx, level):
        ref = ds.DocumentRef(
            doc_id=real_docx.doc_id, path=real_docx.path, title=real_docx.title,
            department=real_docx.department, version=real_docx.version,
            category=real_docx.category, access_level=level, kind=real_docx.kind,
        )
        monkeypatch.setattr(ds, "load_document", lambda doc_id: ref)

    def test_student_denied_faculty_document(self, client, tokens, real_docx, monkeypatch):
        self._patch_level(monkeypatch, real_docx, "Faculty")
        r = client.get(f"/api/documents/{real_docx.doc_id}/view", headers=_hdr(tokens["Student"]))
        assert r.status_code == 403

    def test_faculty_allowed_faculty_document(self, client, tokens, real_docx, monkeypatch):
        self._patch_level(monkeypatch, real_docx, "Faculty")
        r = client.get(f"/api/documents/{real_docx.doc_id}/view", headers=_hdr(tokens["Faculty"]))
        assert r.status_code == 200

    def test_admin_allowed_confidential_document(self, client, tokens, real_docx, monkeypatch):
        self._patch_level(monkeypatch, real_docx, "Confidential")
        r = client.get(f"/api/documents/{real_docx.doc_id}/view", headers=_hdr(tokens["Admin"]))
        assert r.status_code == 200

    def test_student_denied_confidential_document(self, client, tokens, real_docx, monkeypatch):
        self._patch_level(monkeypatch, real_docx, "Confidential")
        r = client.get(f"/api/documents/{real_docx.doc_id}/file", headers=_hdr(tokens["Student"]))
        assert r.status_code == 403


# ── Backward compatibility ──────────────────────────────────────────────────

class TestBackwardCompat:
    def test_existing_endpoints_present(self, client):
        paths = {r.path for r in client.app.routes if hasattr(r, "path")}
        for p in ("/api/auth/login", "/api/chat", "/api/chat/auth/stream",
                  "/api/history", "/api/upload", "/api/users"):
            assert p in paths, f"regressed: {p} missing"

    def test_new_document_routes_registered(self, client):
        paths = {r.path for r in client.app.routes if hasattr(r, "path")}
        for p in ("/api/documents/{doc_id}/view", "/api/documents/{doc_id}/file",
                  "/api/documents/{doc_id}/meta"):
            assert p in paths


# ── Frontend wiring (regression guard for the openDoc-undefined bug) ─────────

class TestFrontendWiring:
    """
    Guards the citation-click → document-viewer integration end of the wire:
      - inline-handler functions are exposed on window (so onclick can resolve them)
      - the citation render path is present
      - static assets are served no-cache so updated JS actually reaches the browser
    """

    def test_app_js_exposes_inline_handlers_on_window(self, client):
        js = client.get("/app.js").text
        assert "Object.assign(window" in js          # explicit global export block
        for fn in ("openDoc", "closeDoc", "downloadDoc", "sendMsg", "doLogin"):
            assert fn in js, f"{fn} missing from app.js"

    def test_app_js_wires_citation_click_to_endpoint(self, client):
        js = client.get("/app.js").text
        assert 'onclick="openDoc(' in js                       # citation is clickable
        assert "/api/documents/" in js                          # calls the viewer endpoint
        assert "function openDoc" in js                          # handler defined

    def test_static_assets_served_no_cache(self, client):
        for path in ("/app.js", "/styles.css", "/"):
            r = client.get(path)
            assert r.status_code == 200
            assert "no-cache" in r.headers.get("cache-control", ""), f"{path} is cacheable"
