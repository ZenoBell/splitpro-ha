import type { NextApiRequest, NextApiResponse } from 'next';
import { db } from '~/server/db';
import { validateApiKey } from '~/lib/ha-auth';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (!validateApiKey(req, res)) {
    return;
  }
  if (req.method !== 'DELETE') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { id } = req.query as { id: string };
  const userEmail = req.query['user_email'] as string | undefined;
  if (!userEmail) {
    return res.status(400).json({ error: 'user_email is required' });
  }

  const user = await db.user.findUnique({ where: { email: userEmail } });
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }

  const expense = await db.expense.findUnique({
    where: { id },
    include: { expenseParticipants: true },
  });

  if (!expense || expense.deletedAt) {
    return res.status(404).json({ error: 'Expense not found' });
  }

  const canDelete = expense.addedBy === user.id || expense.paidBy === user.id;
  if (!canDelete) {
    return res
      .status(403)
      .json({ error: 'Only the expense creator or payer can delete this expense' });
  }

  await db.expense.update({
    where: { id },
    data: { deletedAt: new Date() },
  });

  return res.status(200).json({ success: true, deleted_id: id });
}
