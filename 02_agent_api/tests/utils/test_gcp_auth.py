import pytest

from src.utils.gcp_auth import cloud_run_audience


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://03-mcp-server-abc-uc.a.run.app/mcp",
            "https://03-mcp-server-abc-uc.a.run.app",
        ),
        ("http://localhost:8000/mcp", "http://localhost:8000"),
        (
            "https://service.example/mcp?debug=true#fragment",
            "https://service.example",
        ),
    ],
)
def test_cloud_run_audience_uses_service_origin(url: str, expected: str) -> None:
    assert cloud_run_audience(url) == expected


@pytest.mark.parametrize("url", ["", "/mcp", "localhost:8000/mcp"])
def test_cloud_run_audience_rejects_non_absolute_urls(url: str) -> None:
    with pytest.raises(ValueError, match="URL de servicio inválida"):
        cloud_run_audience(url)
