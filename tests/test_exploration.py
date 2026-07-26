import asyncio

from httpx import AsyncClient

from app.services import exploration_service
from tests.conftest import token_for


async def _auth(client: AsyncClient, device_id: str = "device-A") -> dict[str, str]:
    return {"Authorization": f"Bearer {await token_for(client, device_id)}"}


async def test_push_is_idempotent_union(client: AsyncClient) -> None:
    headers = await _auth(client)
    r1 = await client.post("/api/v1/exploration/cells", json={"cells": ["a", "b"]}, headers=headers)
    assert r1.status_code == 204
    # Re-post an overlapping set → no duplicates.
    r2 = await client.post(
        "/api/v1/exploration/cells", json={"cells": ["a", "b", "c"]}, headers=headers
    )
    assert r2.status_code == 204

    got = await client.get("/api/v1/exploration/cells", headers=headers)
    assert sorted(got.json()["cells"]) == ["a", "b", "c"]


async def test_push_tolerates_duplicates_within_one_payload(client: AsyncClient) -> None:
    headers = await _auth(client)
    res = await client.post(
        "/api/v1/exploration/cells", json={"cells": ["x", "x", "y"]}, headers=headers
    )
    assert res.status_code == 204
    got = await client.get("/api/v1/exploration/cells", headers=headers)
    assert sorted(got.json()["cells"]) == ["x", "y"]


async def test_concurrent_pushes_do_not_conflict(client: AsyncClient) -> None:
    """The mobile foreground watcher and background task can flush at once."""
    headers = await _auth(client)
    payload = {"cells": ["p", "q", "r"]}
    results = await asyncio.gather(
        client.post("/api/v1/exploration/cells", json=payload, headers=headers),
        client.post("/api/v1/exploration/cells", json=payload, headers=headers),
    )
    assert [r.status_code for r in results] == [204, 204]
    got = await client.get("/api/v1/exploration/cells", headers=headers)
    assert sorted(got.json()["cells"]) == ["p", "q", "r"]


async def test_cursor_always_delivers_new_cells(client: AsyncClient) -> None:
    """
    The guarantee is that nothing is ever MISSED, not that nothing repeats.

    A final page's cursor is deliberately rewound a few seconds so a write that
    commits just after the read is re-delivered rather than lost; the client
    merges by union, so the overlap is free.
    """
    headers = await _auth(client)
    await client.post("/api/v1/exploration/cells", json={"cells": ["a", "b"]}, headers=headers)
    first = await client.get("/api/v1/exploration/cells", headers=headers)
    cursor = first.json()["cursor"]

    await client.post("/api/v1/exploration/cells", json={"cells": ["c"]}, headers=headers)
    second = (
        await client.get("/api/v1/exploration/cells", params={"since": cursor}, headers=headers)
    ).json()

    assert "c" in second["cells"]


async def test_cursor_is_null_when_nothing_explored(client: AsyncClient) -> None:
    headers = await _auth(client)
    got = await client.get("/api/v1/exploration/cells", headers=headers)
    assert got.json() == {"cells": [], "cursor": None, "has_more": False}


async def test_pull_is_paginated_and_resumable(client: AsyncClient) -> None:
    """An unbounded pull would hand a reinstalled client the whole history at once."""
    headers = await _auth(client)
    total = exploration_service.PAGE_SIZE + 25
    await client.post(
        "/api/v1/exploration/cells",
        json={"cells": [f"cell-{i:05d}" for i in range(total)]},
        headers=headers,
    )

    first = (await client.get("/api/v1/exploration/cells", headers=headers)).json()
    assert len(first["cells"]) == exploration_service.PAGE_SIZE
    assert first["has_more"] is True

    rest = (
        await client.get(
            "/api/v1/exploration/cells",
            params={"since": first["cursor"]},
            headers=headers,
        )
    ).json()
    assert len(rest["cells"]) == 25
    assert rest["has_more"] is False
    # Every cell arrives exactly once across the two pages.
    assert len(set(first["cells"]) | set(rest["cells"])) == total


async def test_unparseable_cursor_replays_from_the_start(client: AsyncClient) -> None:
    """
    Cursors are opaque and may outlive an encoding change. Re-sending a set the
    client already has costs nothing (it merges by union); silently returning
    NOTHING would strand the device forever.
    """
    headers = await _auth(client)
    await client.post("/api/v1/exploration/cells", json={"cells": ["a"]}, headers=headers)
    res = await client.get(
        "/api/v1/exploration/cells", params={"since": "garbage"}, headers=headers
    )
    assert res.status_code == 200
    assert res.json()["cells"] == ["a"]


async def test_oversized_push_is_rejected(client: AsyncClient) -> None:
    """Unbounded input would reach the database and surface as a 500."""
    headers = await _auth(client)
    too_many = [f"c{i}" for i in range(exploration_service.PAGE_SIZE * 10)]
    res = await client.post("/api/v1/exploration/cells", json={"cells": too_many}, headers=headers)
    assert res.status_code == 422


async def test_repeated_pulls_converge_and_never_lose_a_cell(client: AsyncClient) -> None:
    """
    The union of everything ever delivered must equal the full set.

    That, not "every page repeats everything", is the property the client
    depends on: it merges pages by union, so re-sending is merely wasteful while
    skipping is data loss from a set that is supposed to be impossible to shrink.
    Cells pushed BETWEEN two polls must arrive too, which is what makes this a
    cursor test rather than a pagination test.
    """
    headers = await _auth(client)
    await client.post("/api/v1/exploration/cells", json={"cells": ["a", "b", "c"]}, headers=headers)

    seen: set[str] = set()
    cursor = None

    for round_index in range(3):
        params = {"since": cursor} if cursor else None
        page = (
            await client.get("/api/v1/exploration/cells", params=params, headers=headers)
        ).json()
        assert page["has_more"] is False
        seen.update(page["cells"])
        cursor = page["cursor"]

        # A cell written after the cursor was issued still has to be delivered.
        if round_index == 0:
            await client.post("/api/v1/exploration/cells", json={"cells": ["d"]}, headers=headers)

    assert seen == {"a", "b", "c", "d"}


async def test_requires_auth(client: AsyncClient) -> None:
    res = await client.post("/api/v1/exploration/cells", json={"cells": ["a"]})
    assert res.status_code == 401


async def test_isolated_per_identity(client: AsyncClient) -> None:
    headers_a = await _auth(client, "device-A")
    headers_b = await _auth(client, "device-B")
    await client.post("/api/v1/exploration/cells", json={"cells": ["a"]}, headers=headers_a)
    res_b = await client.get("/api/v1/exploration/cells", headers=headers_b)
    assert res_b.json()["cells"] == []
