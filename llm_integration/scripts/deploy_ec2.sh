#!/usr/bin/env bash
set -euo pipefail

# Usage: run on EC2 after setting env vars (or pulling from SSM)
# Installs Docker & Compose plugin, sets up app as a service with Gunicorn+Nginx

sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER

# App layout expectation: repo is in ~/app
mkdir -p ~/app
cd ~/app

cat > docker-compose.yml <<'YML'
services:
  web:
    build: .
    container_name: llm_web
    env_file:
      - .env
    command: gunicorn project4.wsgi:application -b 0.0.0.0:8000 --workers 3
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on: []
YML

echo "Deploy: docker compose up -d --build"
docker compose up -d --build
echo "Done. Expose 80/443 via Nginx or ALB; 8000 open for quick test."

