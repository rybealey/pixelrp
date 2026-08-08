import { describe, expect, it } from "vitest";
import { sendId, recvName } from "../src/protocol/headers.ts";

describe("headers", () => {
  it("maps names the bot sends to wire ids", () => {
    expect(sendId("ClientHelloEvent")).toBe(4000);
    expect(sendId("SsoTicketEvent")).toBe(2419);
    expect(sendId("ChatEvent")).toBe(1314);
  });
  it("maps received wire ids back to names", () => {
    expect(recvName(1446)).toBe("ChatComposer");
    expect(recvName(2491)).toBe("AuthenticationOkComposer");
    expect(recvName(160)).toBe("RoomForwardComposer");
  });
  it("throws on unknown send name (typo guard)", () => {
    expect(() => sendId("NoSuchEvent")).toThrow(/unknown/i);
  });
  it("returns undefined for unknown received id", () => {
    expect(recvName(65001)).toBeUndefined();
  });
});
