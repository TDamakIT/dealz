#!/usr/bin/env bash
# Installe Docker Engine + le plugin Compose sur Ubuntu (méthode officielle Docker), puis ajoute ton utilisateur au groupe docker.
set -euo pipefail
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  echo "Docker et Docker Compose sont déjà installés : $(docker --version)"; exit 0
fi
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
echo "Installé. Ferme la session et reconnecte-toi (ou lance : newgrp docker) pour utiliser docker sans sudo."
