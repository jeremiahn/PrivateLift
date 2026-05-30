# PrivateLift 🏋️‍♂️

PrivateLift is a self-hosted, private Django web application designed for powerlifting tracking and programming. Built for absolute privacy, it leverages Docker, Tailscale, and Caddy to host your workouts on your own home Linux server, accessible anywhere in the world (including from the gym floor) without opening a single port to the public internet.

The application features a modern, mobile-friendly interface designed for fat-finger gym use, powered by **Tailwind CSS** and **HTMX** for seamless, single-page interactions without heavy Javascript frameworks.

---

## ✨ Features

*   **Big Three Dashboard**: Track your Squat, Bench Press, and Deadlift maxes on a unified, high-contrast dashboard.
*   **Visual Barbell Plate Calculator**: Click the plate icon next to programmed weights to trigger a beautiful modal breakdown. View a loaded barbell sleeve mockup with color-coded plates (45s, 25s, 10s, 5s, 2.5s) per side and a detailed numeric checklist.
*   **RPE Logging & Badge Indicators**: Expose optional RPE selectors (6-10 scale) when logging, backed by robust validation, and view soft color-coordinated RPE badges next to logged sets on the dashboard and history pages.
*   **Estimated 1RM (e1RM)**: Uses the **Epley Formula** to automatically calculate your estimated 1RM for every working set.
*   **Interactive e1RM Progression Charts**: Premium, responsive line charting on the Stats page. Shows strength progress over time for Squat, Bench, and Deadlift, adapting dynamically to system theme settings with interactive tooltips and lift-specific color branding.
*   **Gym-Friendly UX & Auto-Theme Toggling**: Sleek, high-contrast mobile layout with responsive system theme detection and an on-demand Light/Dark mode toggle switch on the Settings page.
*   **Analytics & Lifetime Tonnage**: Track your lifetime accumulated training volume (tonnage) and reps per exercise, with detailed weekly volume breakdowns.
*   **Data Export**: Download your entire lifting history in a clean, standard CSV format.
*   **DevOps Ready**: Pre-packaged with Docker Compose, Gunicorn, and Caddy. Uses automated merge attributes to protect environments between sandbox and production.


---

## 🏗️ System Architecture

```mermaid
graph TD
    subgraph LAN / Tailnet
        Mac[Mac Pro/MacBook (Local Dev)]
        Phone[Mobile Phone at the Gym]
        Server[Linux Home Server]
    end

    subgraph Linux Home Server Docker Environment
        Caddy[Caddy Container (Port 80/443)]
        Gunicorn[Gunicorn Web Container (Port 8000)]
        DB[(SQLite / db.sqlite3)]
    end

    Mac -- Git Push / Deploy --> Server
    Phone -- HTTPS via Tailscale (MagicDNS) --> Caddy
    Caddy -- Internal reverse_proxy --> Gunicorn
    Gunicorn -- ORM Queries --> DB
```

For a comprehensive explanation of how this architecture was selected, the step-by-step phases of building the codebase, and detailed post-mortems of fascinating bugs (like the Port 666 blockade and the login signal race condition), please refer to the developer chronicle:
👉 **[HOW_BUILT.md](file:///Users/jeremiah.nelson/Documents/privatelift/HOW_BUILT.md)**

---

## 🚀 Quick Start

### Prerequisites
*   [Docker & Docker Compose](https://docs.docker.com/get-docker/)
*   [Tailscale](https://tailscale.com/) (recommended for secure, zero-config remote access)

### 1. Local Sandbox Development (on your Mac)
To run the local sandbox environment on your Mac without port conflicts (runs on port `8080` HTTP):

1.  **Configure environment secrets**:
    Create a `.env` file in the project root:
    ```ini
    DEBUG=True
    SECRET_KEY=your-local-sandbox-development-key-12345
    ALLOWED_HOSTS=localhost,127.0.0.1,192.168.50.70
    ```
2.  **Fire up the Docker containers**:
    ```bash
    docker compose up -d
    ```
    *Note: Docker Compose automatically detects the `docker-compose.override.yml` file, which routes the Caddy server to port `8080` externally and mounts `Caddyfile.local`.*
3.  **Apply database migrations**:
    ```bash
    docker compose exec web python manage.py migrate
    ```
4.  **Create your admin user**:
    ```bash
    docker compose exec web python manage.py createsuperuser
    ```
5.  **Access the app**:
    Open your browser and navigate to:
    *   **Dashboard**: `http://localhost:8080/`
    *   **Admin Panel**: `http://localhost:8080/admin/`

---

## 🛠️ Deployment Checklist (Staging & Production)

To deploy to your home server while protecting environment-specific configurations:

### One-Time Git Merge Driver Setup (on your Mac)
To ensure merges from your staging branch into master do not overwrite your production domain settings and Caddy configs:
```bash
# 1. Define custom merge driver
git config merge.ours.driver true

# 2. Rules are pre-configured in .gitattributes:
# Caddyfile merge=ours
# docker-compose.yml merge=ours
```

### Regular Deployment Flow
Once configured, deploying is safe and completely automated:
```bash
# 1. Check out master/production branch
git checkout master

# 2. Merge staging branch normally (protected configurations are shielded automatically!)
git merge staging -m "Merge latest staging features"

# 3. Push it live to the server
git push production master
```

---

## 🧪 Running Tests

PrivateLift has a highly robust test matrix including view interactions, boundary limits, and security enforcement checks.

### Run via Docker:
```bash
docker compose exec web python manage.py test
```

### Run via Native virtualenv:
```bash
python manage.py test
```
