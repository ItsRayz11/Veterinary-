/**
 * Decides whether a click on a link starts a same-site navigation that will take a moment, so the
 * app can show progress. Pure (no DOM access) so it is unit tested without a browser.
 */
export interface ClickInfo {
  defaultPrevented: boolean;
  button: number;
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
}

export interface LinkInfo {
  /** The anchor's resolved absolute URL (`a.href`). */
  href: string;
  target: string;
  hasDownload: boolean;
}

export function startsNavigation(click: ClickInfo, link: LinkInfo, current: string): boolean {
  if (click.defaultPrevented || click.button !== 0) return false;
  if (click.metaKey || click.ctrlKey || click.shiftKey || click.altKey) return false;
  if (link.hasDownload || (link.target && link.target !== "_self")) return false;

  let to: URL;
  let from: URL;
  try {
    to = new URL(link.href);
    from = new URL(current);
  } catch {
    return false;
  }
  if (to.origin !== from.origin) return false;
  // Same page (with or without a hash): nothing to wait for.
  if (to.pathname === from.pathname && to.search === from.search) return false;
  return true;
}
