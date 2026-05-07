import type { NextApiRequest, NextApiResponse } from 'next';
import { db } from '~/server/db';
import { validateApiKey } from '~/lib/ha-auth';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!validateApiKey(req, res)) {
    return;
  }
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const userEmail = req.query['user_email'] as string | undefined;
  if (!userEmail) {
    return res.status(400).json({ error: 'user_email is required' });
  }

  const user = await db.user.findUnique({ where: { email: userEmail } });
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }

  const memberships = await db.groupUser.findMany({
    where: { userId: user.id },
    include: {
      group: {
        include: {
          groupUsers: { include: { user: { select: { id: true, name: true, email: true } } } },
        },
      },
    },
  });

  const groups = memberships.map((m) => ({
    id: m.group.id,
    name: m.group.name,
    member_count: m.group.groupUsers.length,
    members: m.group.groupUsers.map((gm) => ({
      id: gm.user.id,
      name: gm.user.name,
      email: gm.user.email,
    })),
  }));

  return res.status(200).json({ groups });
}
