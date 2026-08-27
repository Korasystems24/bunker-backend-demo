# Деплой на Ubuntu (публичный IP)

GitHub Actions по SSH закидывает код и поднимает `docker compose`. Postgres
снаружи не слушает — только API на порту 8000.

## 1. Один раз на сервере

```bash
# Docker
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker "$USER"
# перелогиньтесь, чтобы группа docker применилась

sudo mkdir -p /opt/bunker-backend
sudo chown "$USER:$USER" /opt/bunker-backend
```

Ключ для GitHub → сервер (на своём ПК):

```bash
ssh-keygen -t ed25519 -f bunker-deploy -N ""
ssh-copy-id -i bunker-deploy.pub USER@SERVER_IP
# приватный bunker-deploy целиком (включая BEGIN/END) — в secret DEPLOY_SSH_KEY
ssh-keyscan -H SERVER_IP   # вывод — в secret DEPLOY_KNOWN_HOSTS
```

`.env` живёт только на сервере (rsync его не трогает):

```bash
cp /opt/bunker-backend/.env.example /opt/bunker-backend/.env   # после первого деплоя файл появится
# или создайте заранее:
nano /opt/bunker-backend/.env
```

Минимум в `.env`:

```bash
POSTGRES_USER=bunker
POSTGRES_PASSWORD=<сильный пароль>
POSTGRES_DB=bunker
BUNKER_ENVIRONMENT=production
BUNKER_API__EDGE_AUTH_TOKEN=<тот же токен, что DISPATCH__HTTP__AUTH_TOKEN у EdgePC>
BUNKER_API__CORS_ORIGINS=["http://<IP-или-домен-фронта>:5173"]
```

Файрвол: 22 (SSH) и 8000 (API). **5432 не открывать.**

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8000/tcp
sudo ufw enable
```

## 2. Secrets в GitHub

Repo → Settings → Secrets and variables → Actions:

| Secret | Значение |
| --- | --- |
| `DEPLOY_HOST` | публичный IP или DNS |
| `DEPLOY_USER` | linux-пользователь (`ubuntu`, `denis`, …) |
| `DEPLOY_SSH_KEY` | приватный ключ `bunker-deploy` |
| `DEPLOY_KNOWN_HOSTS` | вывод `ssh-keyscan -H IP` |
| `DEPLOY_PATH` | `/opt/bunker-backend` |
| `DEPLOY_PORT` | необязательно, по умолчанию `22` |

## 3. Как катится

Пуш в `main` или Actions → Deploy → Run workflow.

На сервере вручную: `cd /opt/bunker-backend && bash scripts/deploy.sh`.

Deploy загружает `catalog/bunkers.json`: имена обновляются, существующая
геометрия не перезаписывается. Её замена выполняется только вручную командой
`docker compose exec -T api python scripts/seed_catalog.py --replace-geometry`.
`bunker_id` EdgePC может быть любой непустой строкой длиной до 128 символов;
backend не интерпретирует её формат.

Проверка: `curl http://SERVER_IP:8000/readyz`.

EdgePC: `DISPATCH__HTTP__SERVER_URL=http://SERVER_IP:8000/api/v1`.
