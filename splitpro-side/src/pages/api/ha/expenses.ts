import type { NextApiRequest, NextApiResponse } from 'next';
import { db } from '~/server/db';
import { validateApiKey } from '~/lib/ha-auth';

function toStorageUnits(amount: number): bigint {
  return BigInt(Math.round(amount * 100));
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!validateApiKey(req, res)) {
    return;
  }
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const {
    user_email,
    name,
    amount,
    currency,
    category = 'general',
    participants: participantEmails,
    group_id,
    paid_by_email,
    expense_date,
  } = req.body as {
    user_email: string;
    name: string;
    amount: number;
    currency?: string;
    category?: string;
    split_equally?: boolean;
    participants: string[];
    group_id?: number;
    paid_by_email?: string;
    expense_date?: string;
  };

  if (!user_email || !name || !amount || !participantEmails?.length) {
    return res
      .status(400)
      .json({ error: 'Required fields: user_email, name, amount, participants' });
  }

  const allEmails = Array.from(new Set([user_email, ...participantEmails]));
  const users = await db.user.findMany({
    where: { email: { in: allEmails } },
    select: { id: true, email: true, name: true },
  });

  const userMap = new Map(users.map((u) => [u.email, u]));

  const addingUser = userMap.get(user_email);
  if (!addingUser) {
    return res.status(404).json({ error: `User not found: ${user_email}` });
  }

  const paidByEmail = paid_by_email ?? user_email;
  const paidByUser = userMap.get(paidByEmail);
  if (!paidByUser) {
    return res.status(404).json({ error: `Paid-by user not found: ${paidByEmail}` });
  }

  // Validate group membership if group_id provided
  if (group_id !== undefined) {
    const group = await db.group.findFirst({
      where: {
        id: Number(group_id),
        groupUsers: { some: { userId: addingUser.id } },
      },
    });
    if (!group) {
      return res.status(404).json({ error: `Group not found: ${group_id}` });
    }
  }

  const resolvedParticipants = participantEmails
    .map((email) => userMap.get(email))
    .filter((u): u is NonNullable<typeof u> => u !== undefined);

  if (resolvedParticipants.length === 0) {
    return res.status(400).json({ error: 'No valid participants found' });
  }

  const totalAmount = toStorageUnits(amount);
  const participantCount = BigInt(resolvedParticipants.length);
  const equalShare = totalAmount / participantCount;
  const remainder = totalAmount - equalShare * participantCount;

  const participantData = resolvedParticipants.map((p, idx) => ({
    userId: p.id,
    amount: idx === 0 ? equalShare + remainder : equalShare,
  }));

  const expense = await db.expense.create({
    data: {
      name,
      amount: totalAmount,
      currency: currency ?? 'USD',
      category,
      expenseDate: expense_date ? new Date(expense_date) : new Date(),
      groupId: group_id !== undefined ? Number(group_id) : null,
      paidBy: paidByUser.id,
      addedBy: addingUser.id,
      expenseParticipants: { create: participantData },
    },
    include: {
      expenseParticipants: {
        include: { user: { select: { id: true, name: true, email: true } } },
      },
    },
  });

  return res.status(201).json({
    id: expense.id,
    name: expense.name,
    amount: Number(expense.amount) / 100,
    currency: expense.currency,
    category: expense.category,
    date: expense.expenseDate.toISOString(),
    participants: expense.expenseParticipants.map((p) => ({
      email: p.user.email,
      name: p.user.name,
      share: Number(p.amount) / 100,
    })),
  });
}
