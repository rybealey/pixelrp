import { describe, expect, it, vi } from "vitest";
import { mintTicket } from "../src/sso.ts";

describe("mintTicket", () => {
  it("writes a fresh random ticket for the user and returns it", async () => {
    const execute = vi.fn(async () => [{ affectedRows: 1 }]);
    const ticket = await mintTicket({ execute } as never, "ClaudeTest");
    expect(ticket).toMatch(/^bot-[0-9a-f-]{36}$/);
    expect(execute).toHaveBeenCalledWith(
      "UPDATE users SET auth_ticket = ? WHERE username = ?",
      [ticket, "ClaudeTest"],
    );
  });
  it("throws when no row matched", async () => {
    const execute = vi.fn(async () => [{ affectedRows: 0 }]);
    await expect(mintTicket({ execute } as never, "Nobody")).rejects.toThrow(/no user/i);
  });
});
