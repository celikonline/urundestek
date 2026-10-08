import { defineConfig } from "@playwright/test";
import path from "node:path";
const root = path.resolve(process.cwd(), "..");
const python =
  process.platform === "win32"
    ? `"${root}/.venv/Scripts/python.exe"`
    : "python";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  use: { baseURL: "http://localhost:5174", trace: "retain-on-failure" },
  webServer: [
    {
      command: `${python} -m alembic upgrade head && ${python} -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log`,
      cwd: root,
      url: "http://127.0.0.1:8001/api/v1/health",
      reuseExistingServer: false,
      env: {
        APP_ENV: "development",
        COOKIE_SECURE: "false",
        PUBLIC_URL: "http://localhost:5174",
        PYTHONPATH: path.join(root, "backend"),
        DATABASE_URL: `sqlite:///${path.join(root, "data", "e2e.db").replaceAll("\\", "/")}`,
      },
    },
    {
      command: "npm run dev -- --port 5174",
      url: "http://localhost:5174",
      reuseExistingServer: false,
      env: { SUPPORT_API_PROXY: "http://127.0.0.1:8001" },
    },
  ],
});
