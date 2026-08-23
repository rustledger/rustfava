import { get_returns } from "../../api/index.ts";
import type { ReturnsResult } from "../../api/validators.ts";
import { _ } from "../../i18n.ts";
import { Route } from "../route.ts";
import ReturnsSvelte from "./Returns.svelte";

/** The scope a returns calculation was requested for. */
export interface ReturnsParams {
  investments: string;
  income: string;
  currency: string;
  end_date: string;
}

export interface ReturnsReportProps {
  params: ReturnsParams;
  /** The computed figures, or null when no scope has been chosen yet. */
  result: ReturnsResult | null;
  /** The engine's refusal message, if it declined to compute. */
  error: string | null;
}

/** Today as YYYY-MM-DD — the component has no clock, so the host supplies one. */
function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function params_from(url: URL): ReturnsParams {
  const p = url.searchParams;
  return {
    investments: p.get("investments") ?? "",
    income: p.get("income") ?? "",
    currency: p.get("currency") ?? "",
    end_date: p.get("end_date") ?? today(),
  };
}

export const returns = new Route<ReturnsReportProps>(
  "returns",
  ReturnsSvelte,
  async (url) => {
    const params = params_from(url);
    // No scope yet: render the form rather than asking the engine to compute
    // returns over nothing.
    if (params.investments.trim() === "") {
      return { params, result: null, error: null };
    }
    try {
      const result = await get_returns(params);
      return { params, result, error: null };
    } catch (error) {
      // The engine refuses rather than reporting a figure it cannot stand
      // behind, and its message names the ledger problem — so show it instead
      // of a blank table.
      return {
        params,
        result: null,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  },
  () => _("Returns"),
);
