import { defineConfig } from "@playwright/test";
import path from "node:path";

const source = process.env.EDI_SOURCE_ROOT || path.resolve(__dirname, "..");
const python = process.env.EDI_TEST_PYTHON || (process.platform === "win32" ? path.join(source, ".venv/Scripts/python.exe") : "python");
const showcase = process.env.EDI_E2E_SHOWCASE === "true";
const workflowDev = process.env.EDI_E2E_WORKFLOW_DEV === "true";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  use: {baseURL: "http://127.0.0.1:3197", channel: process.env.EDI_BROWSER_CHANNEL || "msedge", trace: "off"},
  webServer: [
    {command: `"${python}" "${source}/tests/e2e_server.py"${showcase ? " --showcase-empty" : ""}`, url: "http://127.0.0.1:8197/health", reuseExistingServer: false,
      env: {PYTHONPATH: source, PYTHON_DOTENV_DISABLED: "1", EDI_E2E_WORKFLOW_DEV: workflowDev ? "true" : "false"}},
    {command: `npm run ${workflowDev ? "dev" : "start"} -- --hostname 127.0.0.1 --port 3197`, url: "http://127.0.0.1:3197", reuseExistingServer: false,
      env: {EDI_ENABLE_DEV_AGENT_FRONTEND: workflowDev ? "true" : "false", EDI_DEV_AGENT_TOKEN: "synthetic-browser-agent-token", EDI_SHOWCASE_MODE: showcase ? "synthetic-scripted" : "", BACKEND_API_URL: "http://127.0.0.1:8197", NEXT_TELEMETRY_DISABLED: "1", EDI_ENABLE_DEV_WORKFLOWS_FRONTEND: workflowDev ? "true" : "false", EDI_DEV_WORKFLOW_TOKEN: "synthetic-browser-workflow-token", EDI_DEV_WORKFLOW_ORIGIN: "http://127.0.0.1:3197"}},
  ],
});
