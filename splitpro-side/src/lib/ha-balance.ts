// Amounts are stored as integers in minor units (÷100 for EUR/USD/GBP etc.).
// This divisor is currency-dependent: JPY uses ÷1 (no decimals), KWD uses ÷1000.
// ÷100 is correct for all 2-decimal currencies and covers ~99% of real-world use.
export function toFloat(value: bigint): number {
  return Number(value) / 100;
}

interface FriendBalanceRow {
  friendId: number;
  amount: bigint;
  currency: string;
  friend: { id: number; name: string | null; email: string | null };
}

export interface FriendBalanceSummary {
  friend_id: number;
  friend_name: string | null;
  friend_email: string | null;
  net: number;
  currencies: { currency: string; amount: number }[];
}

export function aggregateFriendBalances(rows: FriendBalanceRow[]): FriendBalanceSummary[] {
  const byFriend = new Map<
    number,
    { friend: FriendBalanceRow['friend']; byCurrency: Map<string, bigint> }
  >();

  for (const row of rows) {
    if (!byFriend.has(row.friendId)) {
      byFriend.set(row.friendId, { friend: row.friend, byCurrency: new Map() });
    }
    const entry = byFriend.get(row.friendId)!;
    entry.byCurrency.set(row.currency, (entry.byCurrency.get(row.currency) ?? 0n) + row.amount);
  }

  return Array.from(byFriend.values()).map(({ friend, byCurrency }) => {
    const currencies = Array.from(byCurrency.entries())
      .map(([currency, raw]) => ({ currency, amount: parseFloat(toFloat(raw).toFixed(2)) }))
      .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount));
    const rawNet = Array.from(byCurrency.values()).reduce((s, v) => s + v, 0n);
    const net = parseFloat(toFloat(rawNet).toFixed(2));
    return {
      friend_id: friend.id,
      friend_name: friend.name,
      friend_email: friend.email,
      net,
      currencies,
    };
  });
}

interface GroupMembership {
  group: {
    id: number;
    name: string;
    groupBalances: { amount: bigint; currency: string }[];
  };
}

export interface GroupBalanceSummary {
  group_id: number;
  group_name: string;
  net: number;
  currencies: { currency: string; amount: number }[];
}

export function aggregateGroupBalances(memberships: GroupMembership[]): GroupBalanceSummary[] {
  return memberships.map(({ group }) => {
    const byCurrency = new Map<string, bigint>();
    for (const b of group.groupBalances) {
      byCurrency.set(b.currency, (byCurrency.get(b.currency) ?? 0n) + b.amount);
    }
    const currencies = Array.from(byCurrency.entries())
      .map(([currency, raw]) => ({ currency, amount: parseFloat(toFloat(raw).toFixed(2)) }))
      .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount));
    const rawNet = Array.from(byCurrency.values()).reduce((s, v) => s + v, 0n);
    const net = parseFloat(toFloat(rawNet).toFixed(2));
    return { group_id: group.id, group_name: group.name, net, currencies };
  });
}
