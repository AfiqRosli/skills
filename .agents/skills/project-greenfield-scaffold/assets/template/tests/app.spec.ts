import { describe, it, expect } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { normalizeEmail } from "@/utils/email";

describe("spine smoke", () => {
  it("normalizes email", () => {
    expect(normalizeEmail(" User@X.COM ")).toBe("user@x.com");
  });

  it("pinia initializes", () => {
    setActivePinia(createPinia());
    expect(true).toBe(true);
  });
});
