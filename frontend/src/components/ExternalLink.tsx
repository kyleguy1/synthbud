import type { AnchorHTMLAttributes, MouseEvent } from "react";
import { isDesktopRuntime, openExternalUrl } from "../lib/runtime";

type ExternalLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  href: string;
};

export function ExternalLink({
  href,
  onClick,
  rel,
  target,
  children,
  ...props
}: ExternalLinkProps) {
  async function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (event.defaultPrevented || !isDesktopRuntime()) {
      return;
    }

    event.preventDefault();
    await openExternalUrl(href);
  }

  return (
    <a
      {...props}
      href={href}
      rel={rel ?? "noreferrer"}
      target={target ?? "_blank"}
      onClick={(event) => {
        void handleClick(event);
      }}
    >
      {children}
    </a>
  );
}
