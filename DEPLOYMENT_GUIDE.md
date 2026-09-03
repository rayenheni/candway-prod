# 🚀 Guide de Déploiement Candway

Le guide complet et détaillé pour déployer la plateforme **Candway** (Portail Recruteur, Portail Candidat, Studio CV, Interviews IA, Dashboard Administrateur) sur un **VPS Namecheap (Ubuntu)** est disponible dans le fichier suivant :

📖 [**DEPLOYMENT_GUIDE_NAMECHEAP_VPS.md**](./DEPLOYMENT_GUIDE_NAMECHEAP_VPS.md)

---

## ⚡ Résumé rapide de vérification de disponibilité :
- **Frontend SPA (Vite + React)** : ✅ Build testé et validé sans aucune erreur (`npm run build`).
- **Backend (FastAPI + Gunicorn)** : ✅ Compilation Python testée et validée (`python -m compileall backend`).
- **Base de données (Alembic)** : ✅ Migration `m61 (head)` active et prête pour MySQL/MariaDB.
- **Proxy Reverse & Securité (Nginx)** : ✅ `nginx.conf` préconfiguré (HTTPS, WebSocket `/ws/`, API `/api/`, SPA fallback).
- **Docker Compose** : ✅ `Dockerfile` multi-stage & `docker-compose.yml` prêts au déploiement en 1 commande.
