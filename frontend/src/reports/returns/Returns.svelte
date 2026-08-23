<script lang="ts">
  import { formatPercentage } from "../../format.ts";
  import { _ } from "../../i18n.ts";
  import { router } from "../../router.ts";
  import { ctx } from "../../stores/format.ts";
  import type { ReturnsReportProps } from "./index.ts";

  let { params, result, error }: ReturnsReportProps = $props();

  // Editable copies of the URL scope. Deliberately not initialised from
  // `params` directly: the route re-renders this same component instance with
  // new props on navigation, so the effect below is what keeps the inputs
  // following the URL. Seeding them here as well would capture only the first
  // value and leave the form showing a previous scope after back/forward.
  let investments = $state("");
  let income = $state("");
  let currency = $state("");
  let end_date = $state("");

  $effect(() => {
    investments = params.investments;
    income = params.income;
    currency = params.currency;
    end_date = params.end_date;
  });

  function submit(event: SubmitEvent) {
    event.preventDefault();
    router.set_search_param("investments", investments);
    router.set_search_param("income", income);
    router.set_search_param("currency", currency);
    router.set_search_param("end_date", end_date);
  }

  /** The reporting currency the figures are expressed in. */
  let reporting = $derived(currency.trim());

  /**
   * Format a raw decimal string.
   *
   * The engine sends full precision deliberately and leaves formatting to the
   * host, so this is where locale and precision are applied.
   */
  const amount = (value: string): string =>
    reporting === "" ? value : $ctx.amount(Number(value), reporting);

  /** A rate, or an explicit "not defined" — which is not the same as zero. */
  const rate = (value: number | null): string =>
    value == null ? _("n/a") : formatPercentage(value);
</script>

<form onsubmit={submit}>
  <p>
    <label>
      {_("Investment accounts")}
      <input
        bind:value={investments}
        placeholder="Assets:Investments"
        size="30"
      />
    </label>
    <label>
      {_("Income accounts")}
      <input bind:value={income} placeholder="Income:Investments" size="30" />
    </label>
  </p>
  <p>
    <label>
      {_("Currency")}
      <input bind:value={currency} placeholder="USD" size="8" />
    </label>
    <label>
      {_("As of")}
      <input bind:value={end_date} type="date" required />
    </label>
    <button type="submit">{_("Calculate")}</button>
  </p>
  <p class="hint">
    {_(
      "Account names are prefixes: everything beneath them is in scope. Leave the currency empty to use the ledger's first operating currency.",
    )}
  </p>
</form>

{#if error != null}
  <div class="error-state">
    <h3>{_("Returns could not be computed")}</h3>
    <p>{error}</p>
    <p class="hint">
      {_(
        "The engine reports an error rather than a figure it cannot stand behind — fix the ledger issue above and try again.",
      )}
    </p>
  </div>
{:else if result != null}
  <table>
    <tbody>
      <tr>
        <td>{_("Invested")}</td>
        <td class="num">{amount(result.invested)}</td>
      </tr>
      <tr>
        <td>{_("Distributions")}</td>
        <td class="num">{amount(result.distributions)}</td>
      </tr>
      <tr>
        <td>{_("Current value")}</td>
        <td class="num">{amount(result.current_value)}</td>
      </tr>
      <tr>
        <td>{_("Cash flows")}</td>
        <td class="num">{result.cash_flows}</td>
      </tr>
      <tr>
        <td title={_("Money-weighted return (XIRR)")}>
          {_("Money-weighted return")}
        </td>
        <td class="num">{rate(result.money_weighted)}</td>
      </tr>
      <tr>
        <td title={_("Time-weighted return")}>{_("Time-weighted return")}</td>
        <td class="num">{rate(result.time_weighted)}</td>
      </tr>
    </tbody>
  </table>
{/if}

<style>
  .hint {
    color: var(--text-color-lighter);
  }

  .error-state {
    padding: 1em;
    margin: 1em 0;
    border-left: 3px solid var(--error);
  }
</style>
