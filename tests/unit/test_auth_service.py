import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.dto.auth import UserCreate
from app.services.auth_service import AuthService


def _make_service_with_mocked_repo(repo_mock: AsyncMock) -> AuthService:
    service = AuthService.__new__(AuthService)
    service.session = MagicMock()
    service.repo = repo_mock
    return service


@pytest.mark.asyncio
async def test_register_user_success() -> None:
    repo = AsyncMock()
    repo.get_by_email = AsyncMock(return_value=None)
    created_user = MagicMock(
        id=uuid.uuid4(), email="a@b.com", full_name="Alice", is_active=True
    )
    repo.create = AsyncMock(return_value=created_user)
    service = _make_service_with_mocked_repo(repo)

    result = await service.register_user(
        UserCreate(email="a@b.com", password="strongpass1", full_name="Alice")
    )

    assert result is created_user
    repo.get_by_email.assert_awaited_once_with("a@b.com")
    args = repo.create.await_args.args[0]
    assert args["email"] == "a@b.com"
    assert args["full_name"] == "Alice"
    assert args["hashed_password"] != "strongpass1"  # must be hashed


@pytest.mark.asyncio
async def test_register_user_duplicate_email_raises_409() -> None:
    repo = AsyncMock()
    repo.get_by_email = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
    service = _make_service_with_mocked_repo(repo)

    with pytest.raises(HTTPException) as exc_info:
        await service.register_user(
            UserCreate(email="dup@b.com", password="strongpass1", full_name="X")
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_authenticate_user_invalid_email_raises_401() -> None:
    repo = AsyncMock()
    repo.get_by_email = AsyncMock(return_value=None)
    service = _make_service_with_mocked_repo(repo)

    with pytest.raises(HTTPException) as exc_info:
        await service.authenticate_user("nobody@b.com", "whatever")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_user_bad_password_raises_401() -> None:
    repo = AsyncMock()
    user = MagicMock(
        id=uuid.uuid4(),
        hashed_password=hash_password("correct-password"),
        is_active=True,
    )
    repo.get_by_email = AsyncMock(return_value=user)
    service = _make_service_with_mocked_repo(repo)

    with pytest.raises(HTTPException) as exc_info:
        await service.authenticate_user("a@b.com", "wrong-password")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_user_inactive_raises_403() -> None:
    repo = AsyncMock()
    user = MagicMock(
        id=uuid.uuid4(),
        hashed_password=hash_password("correct-password"),
        is_active=False,
    )
    repo.get_by_email = AsyncMock(return_value=user)
    service = _make_service_with_mocked_repo(repo)

    with pytest.raises(HTTPException) as exc_info:
        await service.authenticate_user("a@b.com", "correct-password")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_authenticate_user_success_returns_token() -> None:
    repo = AsyncMock()
    user_id = uuid.uuid4()
    user = MagicMock(
        id=user_id,
        hashed_password=hash_password("correct-password"),
        is_active=True,
    )
    repo.get_by_email = AsyncMock(return_value=user)
    service = _make_service_with_mocked_repo(repo)

    token = await service.authenticate_user("a@b.com", "correct-password")
    assert token.token_type == "bearer"
    assert isinstance(token.access_token, str) and token.access_token
