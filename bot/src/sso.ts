import { randomUUID } from "node:crypto";
import type { Pool, ResultSetHeader } from "mysql2/promise";

export async function mintTicket(pool: Pool, username: string): Promise<string> {
  const ticket = `bot-${randomUUID()}`;
  const [result] = (await pool.execute(
    "UPDATE users SET auth_ticket = ? WHERE username = ?",
    [ticket, username],
  )) as [ResultSetHeader, unknown];
  if (result.affectedRows === 0) throw new Error(`no user named ${username}`);
  return ticket;
}
