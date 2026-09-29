import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.restoreAllMocks());

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => ({
    ok: status < 400,
    status,
    json: async () => body,
  })));
}

describe("api", () => {
  it("возвращает полезную нагрузку при успехе", async () => {
    mockFetch(200, { ok: true, llm: { enabled: false }, scenarios: 3 });
    const health = await api.health();
    expect(health.scenarios).toBe(3);
  });

  it("поднимает detail бэкенда как сообщение ошибки", async () => {
    mockFetch(409, { detail: "партия уже завершена" });
    await expect(api.turn("x", "привет")).rejects.toThrow("партия уже завершена");
  });

  it("не падает, если тело ошибки не JSON", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: false,
      status: 502,
      json: async () => { throw new Error("not json"); },
    })));
    await expect(api.scenarios()).rejects.toThrow("HTTP 502");
  });
});
