import uuid

import pytest
import pytest_asyncio

from app.services.database import (
    init_db,
    save_comment,
    get_comments,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Ensure tables exist before tests run."""
    await init_db()


@pytest.mark.asyncio
async def test_save_comment():
    share_id = f"test-share-{uuid.uuid4().hex}"

    comment = await save_comment(
        share_id=share_id,
        finding_id="fnd_123",
        text="Investigating this issue",
        author="tester",
    )

    assert comment["share_id"] == share_id
    assert comment["finding_id"] == "fnd_123"
    assert comment["text"] == "Investigating this issue"
    assert "id" in comment
    assert "created_at" in comment


@pytest.mark.asyncio
async def test_get_comments():
    share_id = f"share-{uuid.uuid4().hex}"

    await save_comment(
        share_id=share_id,
        finding_id="fnd_001",
        text="Comment A",
    )

    await save_comment(
        share_id=share_id,
        finding_id="fnd_002",
        text="Comment B",
    )

    # Different share, should not be returned
    await save_comment(
        share_id=f"other-{uuid.uuid4().hex}",
        finding_id="fnd_001",
        text="Comment C",
    )

    comments = await get_comments(share_id)

    assert len(comments) == 2
    assert comments[0]["text"] == "Comment A"
    assert comments[1]["text"] == "Comment B"


@pytest.mark.asyncio
async def test_comment_parent_id():
    share_id = f"thread-{uuid.uuid4().hex}"

    parent = await save_comment(
        share_id=share_id,
        finding_id="fnd_1",
        text="Parent",
    )

    reply = await save_comment(
        share_id=share_id,
        finding_id="fnd_1",
        text="Reply",
        parent_id=parent["id"],
    )

    assert reply["parent_id"] == parent["id"]