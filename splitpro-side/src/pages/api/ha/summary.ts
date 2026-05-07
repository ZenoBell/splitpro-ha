import type { NextApiRequest, NextApiResponse } from 'next';
import { db } from '~/server/db';
import { validateApiKey } from '~/lib/ha-auth';
import { aggregateFriendBalances, aggregateGroupBalances, toFloat } from '~/lib/ha-balance';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!validateApiKey(req, res)) {
    return;
  }
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const userEmail = req.query['user_email'] as string | undefined;
  if (!userEmail) {
    return res.status(400).json({ error: 'user_email query param is required' });
  }

  const user = await db.user.findUnique({
    where: { email: userEmail },
    select: { id: true, name: true, email: true, hiddenFriendIds: true },
  });
  if (!user) {
    return res.status(404).json({ error: `No user found with email ${userEmail}` });
  }

  const limit = Math.min(parseInt((req.query['limit'] as string) ?? '20', 10), 100);

  const [friendRows, groupMemberships, recentExpenses] = await Promise.all([
    db.balanceView.findMany({
      where: {
        userId: user.id,
        groupId: null,
        friendId: { notIn: user.hiddenFriendIds },
        amount: { not: 0n },
      },
      include: { friend: { select: { id: true, name: true, email: true } } },
    }),
    db.groupUser.findMany({
      where: { userId: user.id },
      select: {
        group: {
          select: {
            id: true,
            name: true,
            groupBalances: {
              where: { userId: user.id },
              select: { amount: true, currency: true },
            },
          },
        },
      },
    }),
    db.expense.findMany({
      where: {
        deletedAt: null,
        expenseParticipants: { some: { userId: user.id } },
      },
      orderBy: { expenseDate: 'desc' },
      take: limit,
      include: {
        group: { select: { id: true, name: true } },
        paidByUser: { select: { id: true, name: true, email: true } },
        expenseParticipants: {
          select: { userId: true, amount: true },
        },
      },
    }),
  ]);

  const friendBalances = aggregateFriendBalances(friendRows);
  const groupBalances = aggregateGroupBalances(groupMemberships);

  const recentWithShare = recentExpenses.map((exp) => {
    const myParticipant = exp.expenseParticipants.find((p) => p.userId === user.id);
    const myShare = myParticipant ? toFloat(myParticipant.amount) : 0;
    const iPaid = exp.paidBy === user.id;
    return {
      id: exp.id,
      name: exp.name,
      amount: toFloat(exp.amount),
      currency: exp.currency,
      my_share: myShare,
      i_paid: iPaid,
      net_effect: iPaid ? toFloat(exp.amount) - myShare : -myShare,
      category: exp.category,
      group: exp.group ? { id: exp.group.id, name: exp.group.name } : null,
      paid_by: { name: exp.paidByUser.name, email: exp.paidByUser.email },
      date: exp.expenseDate.toISOString(),
      created_at: exp.createdAt.toISOString(),
    };
  });

  const totalFriendNet = parseFloat(friendBalances.reduce((s, b) => s + b.net, 0).toFixed(2));
  const totalGroupNet = parseFloat(groupBalances.reduce((s, b) => s + b.net, 0).toFixed(2));
  const totalNet = parseFloat((totalFriendNet + totalGroupNet).toFixed(2));

  return res.status(200).json({
    user: { id: user.id, name: user.name, email: user.email },
    summary: {
      total_balance: totalNet,
      friend_balance: totalFriendNet,
      group_balance: totalGroupNet,
      you_are_owed: parseFloat(Math.max(0, totalNet).toFixed(2)),
      you_owe: parseFloat(Math.abs(Math.min(0, totalNet)).toFixed(2)),
    },
    friend_balances: friendBalances,
    group_balances: groupBalances,
    recent_expenses: recentWithShare,
  });
}
