from app_testing_base.db.cleanup import clean_db_after_test
from app_testing_base.utils.random import random_email, random_string

__all__ = [
    "clean_db_after_test",
    "cleanup_resource",
    "create_and_get",
    "random_email",
    "random_string",
]


async def create_and_get(client, endpoint: str, data: dict) -> dict:
    """Create a resource via API and return the response data."""
    response = await client.post(endpoint, json=data)
    assert response.status_code == 201, f"Create failed: {response.text}"
    return response.json()


async def cleanup_resource(client, endpoint: str, resource_id: str):
    """Delete a resource via API."""
    await client.delete(f"{endpoint}/{resource_id}")
