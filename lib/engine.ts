import data from "../data/logic.json";

export type Purpose = "gaming" | "work" | "creative" | "general";
export type Budget = "low" | "mid" | "high";

export type Input = {
  purpose: Purpose;
  budget: Budget;
};

export type Product = {
  id: string;
  name: string;
  category: string;
  budget: string;
  affiliate_url: string;
};

export type RankedProduct = Product & { rank: number };

/**
 * Deterministic, rule-based recommendation engine.
 *
 * Behaviour:
 *  - Always prioritises an exact rule match (purpose + budget).
 *  - Falls back to the top 3 products if no rule matches.
 *  - Always returns at most 3 ranked products.
 *  - Affiliate URLs are passed through exactly as stored in logic.json.
 */
export function getRecommendation(input: Input): RankedProduct[] {
  const rule = data.rules.find(
    (r) => r.if.purpose === input.purpose && r.if.budget === input.budget
  );

  const products: (Product | undefined)[] = rule
    ? rule.recommendations.map((id) =>
        data.products.find((p) => p.id === id)
      )
    : data.products.slice(0, 3);

  return products
    .filter((p): p is Product => Boolean(p))
    .slice(0, 3)
    .map((p, index) => ({
      rank: index + 1,
      ...p,
      affiliate_url: p.affiliate_url,
    }));
}
