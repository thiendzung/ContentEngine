"use client";

import { useParams } from "next/navigation";

import { OperatorCaseWorkspace } from "../../../../components/operator/operator-case-workspace";
import "../../operator.css";

export default function JournalOperatorCasePage() {
  const params = useParams<{ caseId: string }>();
  return <OperatorCaseWorkspace caseId={params.caseId} />;
}
