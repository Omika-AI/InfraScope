const path = require("path");
const root = path.resolve(__dirname);

module.exports = {
  apps: [
    {
      name: "infrascope-backend",
      script: path.join(root, "backend", "venv", "bin", "uvicorn"),
      args: "app.main:app --host 0.0.0.0 --port 8010",
      cwd: path.join(root, "backend"),
      interpreter: "none",
      watch: false,
      autorestart: true,
      max_restarts: 10,
    },
    {
      name: "infrascope-frontend",
      script: "npx",
      args: "serve -s dist -l 3004",
      cwd: path.join(root, "frontend"),
      interpreter: "none",
      watch: false,
      autorestart: true,
      max_restarts: 10,
    },
  ],
};
