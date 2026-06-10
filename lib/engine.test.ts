import { describe, expect, it } from "vitest";
import { getRecommendation } from "./engine";

describe("getRecommendation", () => {
  it("returns the rule-matched product for gaming + mid", () => {
    const result = getRecommendation({ purpose: "gaming", budget: "mid" });
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("p1");
    expect(result[0].rank).toBe(1);
  });

  it("returns the rule-matched product for work + low", () => {
    const result = getRecommendation({ purpose: "work", budget: "low" });
    expect(result[0].id).toBe("p2");
  });

  it("returns the rule-matched product for creative + high", () => {
    const result = getRecommendation({ purpose: "creative", budget: "high" });
    expect(result[0].id).toBe("p3");
  });

  it("falls back to the top 3 products when no rule matches", () => {
    const result = getRecommendation({ purpose: "general", budget: "low" });
    expect(result).toHaveLength(3);
    expect(result.map((p) => p.id)).toEqual(["p1", "p2", "p3"]);
  });

  it("never returns more than 3 products", () => {
    const result = getRecommendation({ purpose: "general", budget: "high" });
    expect(result.length).toBeLessThanOrEqual(3);
  });

  it("ranks results sequentially starting at 1", () => {
    const result = getRecommendation({ purpose: "general", budget: "mid" });
    result.forEach((product, index) => {
      expect(product.rank).toBe(index + 1);
    });
  });

  it("passes affiliate urls through unmodified", () => {
    const result = getRecommendation({ purpose: "gaming", budget: "mid" });
    expect(result[0].affiliate_url).toBe("https://amazon.co.uk/dp/example1");
  });

  it("is deterministic across repeated calls", () => {
    const a = getRecommendation({ purpose: "creative", budget: "high" });
    const b = getRecommendation({ purpose: "creative", budget: "high" });
    expect(a).toEqual(b);
  });
});
