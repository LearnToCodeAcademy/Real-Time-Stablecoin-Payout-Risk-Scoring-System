import { describe, expect, it } from "vitest";
import { percent, shortAddress } from "./utils";

describe("console formatting", () => {
  it("shortens wallet addresses without hiding both ends", () => {
    expect(shortAddress(`0x${"a".repeat(40)}`)).toBe("0xaaaaa...aaaaa");
  });

  it("formats model probabilities as percentages", () => {
    expect(percent(0.85314)).toBe("85.3%");
    expect(percent(null)).toBe("n/a");
  });
});
