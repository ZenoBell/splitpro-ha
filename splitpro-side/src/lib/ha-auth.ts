import type { NextApiRequest, NextApiResponse } from 'next';

export function validateApiKey(req: NextApiRequest, res: NextApiResponse): boolean {
  const apiKey = process.env.HA_API_KEY;

  if (!apiKey) {
    res.status(500).json({ error: 'HA_API_KEY is not configured on the server.' });
    return false;
  }

  const provided = req.headers['x-ha-api-key'] ?? (req.query['api_key'] as string | undefined);

  if (!provided || provided !== apiKey) {
    res.status(401).json({ error: 'Unauthorized - invalid or missing API key.' });
    return false;
  }

  return true;
}
