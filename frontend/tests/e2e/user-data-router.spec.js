import { test, expect } from '@playwright/test';

// Exercises backend/app/routers/user_data.py end to end over real HTTP
// (no mocking) to confirm the shared list/delete/clear helpers behave
// identically to the pre-refactor per-resource implementations, for both
// the history and favorites resources, and don't leak data across users.

function uniqueEmail(label) {
  return `${label}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

async function signup(request, email) {
  const res = await request.post('/auth/signup', {
    data: { email, password: 'securepassword123' },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return { token: body.access_token, headers: { Authorization: `Bearer ${body.access_token}` } };
}

for (const resource of [
  {
    name: 'history',
    listPath: '/user/history',
    itemPath: (id) => `/user/history/${id}`,
    payload: () => ({
      action: 'analyze',
      code: 'def hello(): pass',
      result_json: '{"status": "ok"}',
    }),
    notFoundDetail: 'History record not found',
  },
  {
    name: 'favorites',
    listPath: '/user/favorites',
    itemPath: (id) => `/user/favorites/${id}`,
    payload: () => ({
      title: 'My snippet',
      action: 'analyze',
      code: 'def hello(): pass',
      result_json: '{"status": "ok"}',
    }),
    notFoundDetail: 'Favorite not found',
  },
]) {
  test.describe(`${resource.name} router`, () => {
    test(`create, list (paginated), delete-one and clear-all round trip`, async ({ request }) => {
      const { headers } = await signup(request, uniqueEmail(`user-${resource.name}`));

      const ids = [];
      for (let i = 0; i < 3; i++) {
        const res = await request.post(resource.listPath, { headers, data: resource.payload() });
        expect(res.status()).toBe(200);
        ids.push((await res.json()).id);
      }

      // Pagination: limit=2 should return only the 2 most recent records.
      const paged = await request.get(`${resource.listPath}?limit=2&offset=0`, { headers });
      expect(paged.ok()).toBeTruthy();
      const pagedBody = await paged.json();
      expect(pagedBody).toHaveLength(2);
      expect(pagedBody[0].id).toBe(ids[2]);
      expect(pagedBody[1].id).toBe(ids[1]);

      const full = await request.get(resource.listPath, { headers });
      expect((await full.json())).toHaveLength(3);

      // Delete one record, then confirm it's gone and the rest remain.
      const del = await request.delete(resource.itemPath(ids[0]), { headers });
      expect(del.status()).toBe(200);

      const afterDelete = await request.get(resource.listPath, { headers });
      const remainingIds = (await afterDelete.json()).map((r) => r.id);
      expect(remainingIds.sort()).toEqual([ids[1], ids[2]].sort());

      // Deleting the same record again must 404 with the resource's own message.
      const redelete = await request.delete(resource.itemPath(ids[0]), { headers });
      expect(redelete.status()).toBe(404);
      expect((await redelete.json()).detail).toBe(resource.notFoundDetail);

      // Clear-all reports the correct remaining count and empties the list.
      const clear = await request.delete(resource.listPath, { headers });
      expect(clear.status()).toBe(200);
      expect((await clear.json()).deleted).toBe(2);

      const afterClear = await request.get(resource.listPath, { headers });
      expect(await afterClear.json()).toEqual([]);
    });

    test('one user cannot read or delete another user\'s records', async ({ request }) => {
      const owner = await signup(request, uniqueEmail(`owner-${resource.name}`));
      const intruder = await signup(request, uniqueEmail(`intruder-${resource.name}`));

      const create = await request.post(resource.listPath, {
        headers: owner.headers,
        data: resource.payload(),
      });
      const ownedId = (await create.json()).id;

      // The intruder's own list must not include the owner's record.
      const intruderList = await request.get(resource.listPath, { headers: intruder.headers });
      expect((await intruderList.json()).map((r) => r.id)).not.toContain(ownedId);

      // Deleting by ID cross-user must 404, not succeed or leak existence.
      const crossDelete = await request.delete(resource.itemPath(ownedId), {
        headers: intruder.headers,
      });
      expect(crossDelete.status()).toBe(404);

      // The record must still exist for its real owner afterwards.
      const ownerList = await request.get(resource.listPath, { headers: owner.headers });
      expect((await ownerList.json()).map((r) => r.id)).toContain(ownedId);
    });

    test('requires authentication', async ({ request }) => {
      const res = await request.get(resource.listPath);
      expect(res.status()).toBe(401);
    });
  });
}
