import WorkflowClient from "./workflow-client";

export default function WorkflowsPage() {
  const available = process.env.NODE_ENV === "development" && process.env.EDI_ENABLE_DEV_WORKFLOWS_FRONTEND === "true" && !!process.env.EDI_DEV_WORKFLOW_TOKEN;
  return <WorkflowClient available={available}/>;
}
