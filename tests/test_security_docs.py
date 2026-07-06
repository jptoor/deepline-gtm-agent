from pathlib import Path


def test_security_policy_documents_agent_boundary():
    security = Path("SECURITY.md").read_text()

    assert "thin agent broker" in security
    assert "Deepline owns GTM execution" in security
    assert "Do not add local provider waterfalls" in security
    assert "Run `/doctor`" in security


def test_setup_docs_do_not_claim_wildcard_cors_default():
    setup = Path("SETUP.md").read_text()
    readme = Path("README.md").read_text()

    assert "defaults to `*`" not in setup
    assert "defaults to `*`" not in readme
    assert "empty disables browser CORS" in setup
    assert "empty disables browser CORS" in readme
