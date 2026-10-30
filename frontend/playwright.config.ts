import { defineConfig } from "@playwright/test";
import path from "node:path";

const source = process.env.EDI_SOURCE_ROOT || path.resolve(__dirname, "..");
const python = process.env.EDI_TEST_PYTHON || (process.platform === "win32" ? path.join(source, ".venv/Scripts/python.exe") : "python");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  use: {baseURL: "http://127.0.0.1:3197", channel: process.env.EDI_BROWSER_CHANNEL || "msedge", trace: "off"},
  webServer: [
    {command: `"${python}" "${source}/tests/e2e_server.py"`, url: "http://127.0.0.1:8197/health", reuseExistingServer: false,
      env: {PYTHONPATH: source, PYTHON_DOTENV_DISABLED: "1"}},
    {command: "npm run start -- --port 3197", url: "http://127.0.0.1:3197", reuseExistingServer: false,
      env: {BACKEND_API_URL: "http://127.0.0.1:8197", NEXT_TELEMETRY_DISABLED: "1"}},
  ],
});
