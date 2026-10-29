import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

const VARIANT = {
  primary:
    "bg-primary text-primary-fg shadow-sm hover:opacity-90 active:translate-y-px active:shadow-none",
  secondary: "neo text-text",
  danger: "bg-danger text-primary-fg hover:opacity-90",
} as const;

export function Button({
  variant = "primary",
  loading = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof VARIANT;
  loading?: boolean;
}) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex min-h-11 items-center justify-center rounded-lg px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60 ${VARIANT[variant]} ${className}`}
    >
      {loading ? "Please wait…" : children}
    </button>
  );
}

const CONTROL =
  "neo-inset min-h-11 w-full rounded-lg border border-border px-3 text-sm focus:border-primary aria-[invalid=true]:border-danger";

export function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-err`} role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export function describedBy(id: string, error?: string, hint?: string) {
  return error ? `${id}-err` : hint ? `${id}-hint` : undefined;
}

export function TextInput({
  error,
  hint,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { id: string; error?: string; hint?: string }) {
  return (
    <input
      {...rest}
      aria-invalid={!!error}
      aria-describedby={describedBy(rest.id, error, hint)}
      className={CONTROL}
    />
  );
}

export function Select({
  error,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { id: string; error?: string }) {
  return (
    <select
      {...rest}
      aria-invalid={!!error}
      aria-describedby={describedBy(rest.id, error)}
      className={CONTROL}
    >
      {children}
    </select>
  );
}

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-surface-2 ${className}`} />;
}
