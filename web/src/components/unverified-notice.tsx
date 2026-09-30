import type { Status } from "@/lib/api";
import { Alert } from "@/components/ui/primitives";

/** Shown on catalogue pages whose record was imported from a public list and not yet reviewed. */
export function UnverifiedNotice({ status, what }: { status: Status; what: string }) {
  if (!status.is_unverified_import) return null;
  return (
    <Alert tone="warn" title="Imported, not reviewed">
      This {what} comes from a public regulator list and has not been checked by a reviewer. A
      listing is an application, not proof of registration or of availability. Do not rely on it for
      clinical decisions; check the product label and the regulator.
    </Alert>
  );
}
