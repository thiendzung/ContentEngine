import { notFound } from "next/navigation";

import { OperatorCaseWorkspace } from "../../../../components/operator/operator-case-workspace";
import type { OperatorUxFixtureState } from "../../../../lib/operator/ux-fixtures";
import "../../operator.css";

const STATES = new Set<OperatorUxFixtureState>([
  "ready",
  "queued",
  "running",
  "blocked",
  "approval",
  "complete",
  "error",
  "stale",
  "empty",
]);

export default async function OperatorUxFixturePage({
  params,
}: {
  params: Promise<{ state: string }>;
}) {
  if (process.env.NEXT_PUBLIC_UX_FIXTURES !== "1") notFound();

  const { state } = await params;
  if (!STATES.has(state as OperatorUxFixtureState)) notFound();

  return (
    <OperatorCaseWorkspace
      caseId={`ux-fixture-${state}`}
      uxInitialReconcileRequired={state === "stale"}
    />
  );
}
