<script lang="ts">
  import type { Snippet } from "svelte";

  import { urlFor } from "../helpers.ts";
  import type { KeySpec } from "../keyboard-shortcuts.ts";
  import { keyboardShortcut } from "../keyboard-shortcuts.ts";
  import { pathname } from "../stores/url.ts";

  interface Props {
    /** Report to generate the URL for. */
    report: string;
    /** Name to display for this link. */
    name: string;
    /** Key combination for the link. */
    key?: KeySpec;
    /** Whether this is a remote link (for which we do not intercept clicks). */
    remote?: true;
    /** Show a bubble with a number */
    bubble?: [number, "error" | "info"];
    children?: Snippet;
  }

  let { report, name, key, remote, bubble, children }: Props = $props();

  /** Whether this is an absolute URL to some other site. */
  const is_external_url = (url: string): boolean =>
    /^[a-z][a-z0-9+.-]*:/iu.test(url) || url.startsWith("//");

  /**
   * Whether this is a path on this instance, already prefixed.
   *
   * Such a page is rendered by the backend (like the help page), which the
   * router handles by loading `?partial=true` and replacing `<article>` - so it
   * must not be marked remote, or the click would reload the whole document.
   */
  const is_prefixed_path = (url: string): boolean => url.startsWith("/");

  let external = $derived(remote === true || is_external_url(report));
  let href = $derived(
    external || is_prefixed_path(report) ? report : $urlFor(`${report}/`),
  );
  let selected = $derived(external ? false : href.includes($pathname));
</script>

<li>
  <a class:selected {href} {@attach keyboardShortcut(key)} data-remote={external ? true : undefined}>
    {name}
    {#if bubble && bubble[0] > 0}
      <span class="bubble" class:error={bubble[1] === "error"}>
        {bubble[0]}
      </span>
    {/if}
  </a>
  {@render children?.()}
</li>

<style>
  a {
    display: block;
    padding: 0.25em 0.5em 0.25em 1em;
    color: inherit;
  }

  a.selected,
  a:hover {
    color: var(--sidebar-hover-color);
    background-color: var(--sidebar-border);
  }

  li {
    display: flex;
    flex-wrap: wrap;
  }

  li:last-child {
    margin-bottom: 0;
    border: none;
  }

  li a:first-child {
    flex: 1;
  }

  .bubble {
    float: right;
    padding: 0 8px;
    font-size: 0.9em;
    color: var(--sidebar-color);
    background-color: var(--sidebar-border);
    border-radius: 12px;
  }

  .error.bubble {
    color: white;
    background-color: var(--error);
  }
</style>
