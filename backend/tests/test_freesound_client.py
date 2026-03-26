from app.ingestion.freesound_client import FreesoundClient


def test_freesound_client_headers():
    client = FreesoundClient(api_token="test-token")
    headers = client._get_headers()
    assert headers["Authorization"] == "Token test-token"

