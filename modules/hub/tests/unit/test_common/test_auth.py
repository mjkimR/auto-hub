from unittest.mock import MagicMock, patch

import pytest
from app.auth import verify_api_key
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_verify_api_key_success():
    mock_auth_config = MagicMock()
    mock_auth_config.APP_SECRET_KEY.get_secret_value.return_value = "my-secret-key"

    with patch("app.auth.get_auth_config", return_value=mock_auth_config):
        # Should not raise exception
        await verify_api_key(x_api_key="my-secret-key")


@pytest.mark.asyncio
async def test_verify_api_key_invalid():
    mock_auth_config = MagicMock()
    mock_auth_config.APP_SECRET_KEY.get_secret_value.return_value = "my-secret-key"

    with patch("app.auth.get_auth_config", return_value=mock_auth_config):
        with pytest.raises(HTTPException) as exc:
            await verify_api_key(x_api_key="wrong-key")
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid or missing API key"


@pytest.mark.asyncio
async def test_verify_api_key_misconfigured():
    mock_auth_config = MagicMock()
    # Simulate missing/unset APP_SECRET_KEY
    mock_auth_config.APP_SECRET_KEY = None

    with patch("app.auth.get_auth_config", return_value=mock_auth_config):
        with pytest.raises(HTTPException) as exc:
            await verify_api_key(x_api_key="any-key")
        assert exc.value.status_code == 500
        assert exc.value.detail == "Invalid or missing API key"
