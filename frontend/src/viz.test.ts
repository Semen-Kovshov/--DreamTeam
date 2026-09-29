import { describe, expect, it } from "vitest";
import { zopaPosition } from "./components/Zopa";
import { tensionTone } from "./components/Meters";

describe("шкала ZOPA", () => {
  it("считает долю для «больше — лучше» (зарплата)", () => {
    expect(zopaPosition(175, 190, 175)).toBe(0);
    expect(zopaPosition(175, 190, 190)).toBe(1);
    expect(zopaPosition(175, 190, 185)).toBeCloseTo(0.667, 2);
  });

  it("считает долю для «меньше — лучше» (цена поставщика)", () => {
    expect(zopaPosition(1400, 1300, 1400)).toBe(0);
    expect(zopaPosition(1400, 1300, 1300)).toBe(1);
    expect(zopaPosition(1400, 1300, 1350)).toBeCloseTo(0.5, 5);
  });

  it("зажимает выход за края", () => {
    expect(zopaPosition(175, 190, 160)).toBe(0);
    expect(zopaPosition(175, 190, 210)).toBe(1);
  });
});

describe("зоны напряжения (палитра «хвоя»)", () => {
  it("красная зона с 65, оранжевая с 45", () => {
    expect(tensionTone(20)).toBe("#d9a12b");
    expect(tensionTone(50)).toBe("#d97a3f");
    expect(tensionTone(70)).toBe("#c04b3c");
  });
});
