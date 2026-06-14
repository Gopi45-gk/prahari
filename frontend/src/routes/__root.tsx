import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold">404</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Section not found in PRAHARI Authority.
        </p>
        <Link to="/" className="mt-6 inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
          Return to Command Center
        </Link>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold">System fault</h1>
        <p className="mt-2 text-sm text-muted-foreground">A subsystem failed to load.</p>
        <button
          onClick={() => { router.invalidate(); reset(); }}
          className="mt-6 inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "PRAHARI Authority — Railway Command & Control" },
      { name: "description", content: "Enterprise-grade railway operations, risk and incident command platform." },
      { name: "theme-color", content: "#060B14" },
      { property: "og:title", content: "PRAHARI Authority" },
      { property: "og:description", content: "Railway Command & Control Platform" },
      { property: "og:type", content: "website" },
    ],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head><HeadContent /></head>
      <body>{children}<Scripts /></body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <BootGate>
        <Outlet />
      </BootGate>
    </QueryClientProvider>
  );
}

function BootGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = router.state.location.pathname;
  useEffect(() => {
    if (typeof window === "undefined") return;
    const splashShown = sessionStorage.getItem("prahari_splash_shown") === "1";
    const isAuthed = (() => {
      try { return !!localStorage.getItem("prahari_auth"); } catch { return false; }
    })();

    // Always show splash first on a fresh tab/load
    if (!splashShown && pathname !== "/splash") {
      router.navigate({ to: "/splash" });
      return;
    }
    // After splash, gate the app behind login
    if (splashShown && !isAuthed && pathname !== "/login" && pathname !== "/splash") {
      router.navigate({ to: "/login" });
    }
  }, [pathname, router]);

  return <>{children}</>;
}


