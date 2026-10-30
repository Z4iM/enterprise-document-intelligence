import InvestigationClient from "./investigation-client";

export const dynamic = "force-dynamic";

export default function InvestigationPage() {
  const unavailableReason = process.env.NODE_ENV !== "development"
    ? "AI investigation currently requires local development mode. It is disabled in production builds."
    : process.env.EDI_ENABLE_DEV_AGENT_FRONTEND !== "true" || !process.env.EDI_DEV_AGENT_TOKEN
      ? "AI investigation is not enabled or configured for this local workspace. Follow the investigation setup in the project README, then restart the frontend."
      : null;
  return <InvestigationClient unavailableReason={unavailableReason}/>;
}
