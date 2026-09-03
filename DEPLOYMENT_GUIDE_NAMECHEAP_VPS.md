# 🚀 Guide de Déploiement Production — Candway Platform sur VPS Namecheap

Ce guide détaillé explique pas à pas comment déployer la plateforme **Candway** (Portail Recruteur, Portail Candidat, Studio CV, Interviews IA, et Dashboard Administrateur) sur un **VPS Namecheap** (Ubuntu 22.04 / 24.04 LTS).

---

## 📑 Table des Matières
1. [Rapport de Vérification de Pré-Déploiement](#1-rapport-de-vérification-de-pré-déploiement)
2. [Prérequis Matériels & Système](#2-prérequis-matériels--système)
3. [Configuration du Domaine & DNS Namecheap](#3-configuration-du-domaine--dns-namecheap)
4. [Préparation du Serveur VPS (Ubuntu)](#4-préparation-du-serveur-vps-ubuntu)
5. [Méthode A : Déploiement Automatisé avec Docker Compose (Recommandé)](#5-méthode-a--déploiement-automatisé-avec-docker-compose-recommandé)
6. [Méthode B : Déploiement Natif (Systemd + Nginx + Gunicorn)](#6-méthode-b--déploiement-natif-systemd--nginx--gunicorn)
7. [Configuration Certificat SSL (Certbot / Let's Encrypt)](#7-configuration-certificat-ssl-certbot--lets-encrypt)
8. [Migrations de Base de Données & Administrateur Initial](#8-migrations-de-base-de-données--administrateur-initial)
9. [Procédure de Mise à Jour (CI/CD / Déploiement Continu)](#9-procédure-de-mise-à-jour-cicd--déploiement-continu)
10. [Sauvegardes Automatiques & Maintenance](#10-sauvegardes-automatiques--maintenance)
11. [Guide de Dépannage (Troubleshooting)](#11-guide-de-dépannage-troubleshooting)

---

## 1. Rapport de Vérification de Pré-Déploiement

Un contrôle de qualité et de compatibilité de la plateforme a été effectué sur le dépôt d'origine :

| Composant | Statut | Résultat du Test | Notes |
| :--- | :---: | :--- | :--- |
| **Frontend React SPA** | ✅ PRÊT | `npm run build` OK (Vite compilation clean) | Bundles JS/CSS optimisés générés dans `dist/` |
| **Backend FastAPI** | ✅ PRÊT | `python -m compileall backend` OK (0 erreurs) | Compatible Python 3.11 - 3.13 |
| **Migrations DB (Alembic)** | ✅ PRÊT | Head migration `m61` active | Compatible MySQL 8.0 & MariaDB 10.6+ |
| **Reverse Proxy Nginx** | ✅ PRÊT | `nginx.conf` configuré | Gestion API `/api/`, WebSockets `/ws/`, SPA fallback `/index.html` |
| **Containerisation** | ✅ PRÊT | `Dockerfile` multi-stage & `docker-compose.yml` valides | Images légères distroless + nginx |
| **Sécurité PII & GDPR** | ✅ PRÊT | Key encryption `CANDWAY_FIELD_ENCRYPTION_KEY` | Chiffrement au repos des CVs et historiques d'entretien |

---

## 2. Prérequis Matériels & Système

Pour faire tourner Candway avec la base MySQL, Redis et le moteur backend FastAPI + Nginx :

- **Plan VPS Namecheap conseillé** : **VPS Pulsar** (ou **Stellar**)
  - **CPU** : 2 vCPU minimum (4 vCPU recommandés pour forte charge IA/CV)
  - **RAM** : 2 Go à 4 Go minimum (4 Go recommandé)
  - **Stockage** : 40 Go SSD NVMe minimum
  - **OS** : Ubuntu 22.04 LTS ou Ubuntu 24.04 LTS (64-bit)

---

## 3. Configuration du Domaine & DNS Namecheap

1. Connectez-vous à votre compte **Namecheap** > **Domain List** > cliquez sur **Manage** à côté de votre domaine (ex: `candway.io`).
2. Allez dans l'onglet **Advanced DNS**.
3. Ajoutez/modifiez les enregistrements DNS suivants :
   - **Enregistrement A** : 
     - Host: `@` | Value: `[IP_PUBLIC_DE_VOTRE_VPS]` | TTL: `Automatic`
   - **Enregistrement CNAME** : 
     - Host: `www` | Value: `candway.io.` | TTL: `Automatic`
4. *(Optionnel pour les e-mails)* Ajoutez un enregistrement **PTR (Reverse DNS)** dans votre panneau VPS Namecheap associant l'IP au nom de domaine pour éviter le classement en SPAM des emails de vérification.

---

## 4. Préparation du Serveur VPS (Ubuntu)

Connectez-vous à votre VPS via SSH :
```bash
ssh root@VOTRE_IP_VPS
```

### 4.1. Mise à jour du système & Installation de UFW (Pare-feu)
```bash
apt update && apt upgrade -y
apt install -y ufw curl git htop unzip tar software-properties-common

# Configuration des règles du pare-feu
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP
ufw allow 443/tcp    # HTTPS
ufw enable
```

### 4.2. Installation de Docker & Docker Compose (Recommandé)
```bash
# Suppression des versions obsolètes
apt remove -y docker docker-engine docker.io containerd runc

# Installation des clés officielles Docker
apt install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Ajout du repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Démarrage automatique
systemctl enable docker
systemctl start docker
```

---

## 5. Méthode A : Déploiement Automatisé avec Docker Compose (Recommandé)

Cette méthode déploie FastAPI, React SPA, MySQL 8.0, Redis 7, Nginx et Prometheus/Grafana dans des conteneurs isolés.

### 5.1. Cloner le Projet sur le VPS
```bash
mkdir -p /var/www
cd /var/www
git clone https://github.com/votre-org/candway.git platform
cd platform
```

### 5.2. Configurer les Variables d'Environnement Production
Copiez le modèle et générez des secrets uniques :
```bash
cp .env.production.example .env
```

Générez vos clés de sécurité à injecter dans le fichier `.env` :
```bash
# 1. SECRET_KEY JWT
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# 2. CANDWAY_FIELD_ENCRYPTION_KEY (Obligatoire pour les données PII)
python3 -c "from cryptography.fernet import Fernet; print('CANDWAY_FIELD_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# 3. Mots de passe MySQL et Redis
openssl rand -base64 24
```

Éditez ensuite le fichier `.env` :
```bash
nano .env
```
Assurez-vous d'avoir renseigné :
```ini
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=votre_secret_key_generee
CANDWAY_FIELD_ENCRYPTION_KEY=votre_cle_fernet_generee
MYSQL_ROOT_PASSWORD=un_mot_de_passe_root_tres_fort
MYSQL_PASSWORD=un_mot_de_passe_app_tres_fort
REDIS_PASSWORD=un_mot_de_passe_redis_fort
DATABASE_URL=mysql+pymysql://candway_user:un_mot_de_passe_app_tres_fort@mysql:3306/candway_db?charset=utf8mb4
REDIS_URL=redis://:un_mot_de_passe_redis_fort@redis:6379/0
ALLOWED_ORIGINS=https://candway.io,https://www.candway.io
ALLOWED_HOSTS=candway.io,www.candway.io

# Clefs d'API IA (Au moins une requise)
GROQ_API_KEY=gsk_...
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=AIza...

# Email SMTP (Gmail / SendGrid / Mailgun)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=contact@candway.io
SMTP_PASSWORD=votre_mot_de_passe_application
```

### 5.3. Créer le Répertoire de Certificats Temporaires pour Nginx
Avant de lancer Docker, créez un répertoire `./certs` pour éviter les erreurs Nginx :
```bash
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -subj "/CN=candway.io"
```

### 5.4. Lancer les Conteneurs
```bash
docker compose build --no-cache
docker compose up -d
```

Vérifiez le statut des conteneurs :
```bash
docker compose ps
```

---

## 6. Méthode B : Déploiement Natif (Systemd + Nginx + Gunicorn)

Si vous préférez installer Python et MySQL directement sur le système sans Docker :

### 6.1. Installer Python, Nginx & MySQL
```bash
apt install -y python3.11 python3.11-venv python3.11-dev mysql-server redis-server nginx certbot python3-certbot-nginx
```

### 6.2. Configurer MySQL
```bash
mysql_secure_installation
```
Connectez-vous à MySQL et créez la base de données :
```sql
CREATE DATABASE candway_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'candway_user'@'localhost' IDENTIFIED BY 'MOT_DE_PASSE_SECURISE';
GRANT ALL PRIVILEGES ON candway_db.* TO 'candway_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 6.3. Installer l'Environnement Virtuel Python
```bash
cd /var/www/platform
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn uvicorn
```

### 6.4. Compiler le Frontend React SPA
```bash
cd /var/www/platform/frontend
npm install
npm run build
# Le résultat est compilé dans dist/
```

### 6.5. Créer le Service Systemd pour FastAPI (`/etc/systemd/system/candway.service`)
```ini
[Unit]
Description=Candway FastAPI Backend Service
After=network.target mysql.service redis-server.service

[Service]
User=root
WorkingDirectory=/var/www/platform
EnvironmentFile=/var/www/platform/.env
ExecStart=/var/www/platform/venv/bin/gunicorn -k uvicorn.workers.UvicornWorker backend.app:create_app() --bind 127.0.0.1:8000 --workers 4 --timeout 120
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Activez et démarrez le service :
```bash
systemctl daemon-reload
systemctl enable candway
systemctl start candway
systemctl status candway
```

---

## 7. Configuration Certificat SSL (Certbot / Let's Encrypt)

Obtenez un certificat SSL gratuit et valide avec renouvellement automatique :

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d candway.io -d www.candway.io
```

Certbot reconfigurera automatiquement votre fichier `/etc/nginx/sites-available/default` ou `nginx.conf` pour activer la redirection HTTP -> HTTPS de manière transparente.

Tester le renouvellement automatique :
```bash
certbot renew --dry-run
```

---

## 8. Migrations de Base de Données & Administrateur Initial

Une fois le backend démarré et connecté à MySQL, exécutez la migration des tables Alembic :

### Avec Docker Compose :
```bash
docker compose exec backend alembic upgrade head
```

### En mode Natif :
```bash
cd /var/www/platform
source venv/bin/activate
alembic upgrade head
```

---

## 9. Procédure de Mise à Jour (CI/CD / Déploiement Continu)

Pour déployer une mise à jour de la plateforme sans interruption de service :

```bash
cd /var/www/platform
git pull origin main

# En mode Docker Compose :
docker compose build backend nginx
docker compose up -d --no-deps backend nginx
docker compose exec backend alembic upgrade head

# En mode Natif :
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
cd frontend && npm install && npm run build && cd ..
systemctl restart candway
systemctl restart nginx
```

---

## 10. Sauvegardes Automatiques & Maintenance

### 10.1. Script de Sauvegarde MySQL Cron (`/etc/cron.daily/backup-candway-db`)
Créez un script de sauvegarde automatique quotidien :

```bash
cat << 'EOF' > /etc/cron.daily/backup-candway-db
#!/bin/bash
BACKUP_DIR="/var/backups/candway"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Docker Compose backup:
docker exec $(docker ps -qf "name=mysql") mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" candway_db | gzip > "$BACKUP_DIR/candway_db_$DATE.sql.gz"

# Retention de 14 jours
find $BACKUP_DIR -type f -mtime +14 -name "*.sql.gz" -delete
EOF

chmod +x /etc/cron.daily/backup-candway-db
```

---

## 11. Guide de Dépannage (Troubleshooting)

### 1. Consulter les logs du Backend FastAPI :
```bash
# Docker :
docker compose logs -f backend

# Natif :
journalctl -u candway -f --no-tail
```

### 2. Consulter les logs Nginx :
```bash
tail -f /var/log/nginx/error.log
```

### 3. Vérifier le Healthcheck API :
```bash
curl -I http://127.0.0.1:8000/api/v1/monitoring/health
```

### 4. Réinitialisation des Ssessions Redis en cas de blocage Rate Limit :
```bash
# Docker :
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" FLUSHALL

# Natif :
redis-cli FLUSHALL
```

---
*Guide créé pour le déploiement de Candway Intelligence Platform sur VPS Namecheap.*
