import { Component, type ErrorInfo, type ReactNode } from 'react';
import { isRouteErrorResponse, useRouteError } from 'react-router';
import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react';

function ErrorView({ title, message, reset }: { title: string; message: string; reset?: () => void }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#FAF7FF] p-6 dark:bg-[#0D0A1A]">
      <section className="w-full max-w-lg rounded-3xl border border-violet-200/60 bg-white/85 p-8 text-center shadow-xl shadow-violet-500/10 backdrop-blur-xl dark:border-violet-500/20 dark:bg-[#171027]/90">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400">
          <AlertTriangle className="h-7 w-7" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">{message}</p>
        <div className="mt-7 flex justify-center gap-3">
          <button onClick={() => window.history.back()} className="inline-flex items-center gap-2 rounded-xl border border-violet-200 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-violet-50 dark:border-violet-500/20 dark:text-gray-200 dark:hover:bg-violet-500/10">
            <ArrowLeft className="h-4 w-4" /> Go back
          </button>
          <button onClick={reset || (() => window.location.reload())} className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700">
            <RefreshCw className="h-4 w-4" /> Try again
          </button>
        </div>
      </section>
    </main>
  );
}

export function RouteErrorPage() {
  const error = useRouteError();
  if (isRouteErrorResponse(error)) {
    return <ErrorView title={`${error.status} ${error.statusText}`} message={typeof error.data === 'string' ? error.data : 'The requested page could not be loaded.'} />;
  }
  const message = error instanceof Error ? error.message : 'An unexpected interface error occurred.';
  return <ErrorView title="Something went wrong" message={message} />;
}

interface BoundaryState { error: Error | null }

export class AppErrorBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Replace with a PII-safe observability integration in production.
    console.error('Candway UI error', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return <ErrorView title="Candway could not render this view" message={this.state.error.message} reset={() => this.setState({ error: null })} />;
    }
    return this.props.children;
  }
}
