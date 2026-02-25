module.exports = {
  apps: [
    {
      name: "infrascope-backend",
      script: "./venv/bin/uvicorn",
      args: "app.main:app --host 0.0.0.0 --port 8010",
      cwd: "./backend",
      interpreter: "none",
      watch: false,
      autorestart: true,
      max_restarts: 10,
    },
    {
      name: "infrascope-frontend",
      script: "npx",
      args: "serve -s dist -l 3004",
      cwd: "./frontend",
      interpreter: "none",
      watch: false,
      autorestart: true,
      max_restarts: 10,
    },
  ],
};
