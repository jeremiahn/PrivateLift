# The PrivateLift Chronicle: How the App Was Built

This document provides a comprehensive, step-by-step developer history and architectural manual for **PrivateLift**. It details how the application was built in dialogue with the Gemini web interface, taking it from a raw set of weightlifting requirements to a fully virtualized, secured, and automated containerized Django application.

---

## 🏗️ Architectural Overview & System Design

PrivateLift is designed to run securely within a **Tailscale virtual private mesh network (Tailnet)**. This completely eliminates the need to expose ports on a home router (no public port forwarding), providing absolute privacy while making the app easily accessible at the gym from a phone.

### 🌐 Network & Deployment Topology

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

### ⚙️ Environment Configuration Strategy
The application manages local sandbox development and production environments elegantly through Git attributes and Docker overrides:
*   **Local Development (Mac Sandbox)**: Runs on port `8080` (HTTP) mapped to container port `80`, using `Caddyfile.local` (dumbed-down configuration) and `docker-compose.override.yml`. This keeps local git status clean and avoids macOS port `80` permission restrictions.
*   **Production Environment (Server)**: Runs on ports `80` and `443` (with internal Tailscale TLS certificates), reverse proxying directly to Gunicorn on port `8000`.

---

## 🛠️ Step-by-Step Build Phases

### Phase 1: Tech Stack Selection & Base Setup
The core requirements were simple: track the "Big Three" lifts (Squat, Bench Press, Deadlift), perform automated programming, and package it for seamless deployment.

1.  **Tech Stack Selection**:
    *   **Backend**: **Python / Django 5.x** — chosen for its built-in admin dashboard, powerful ORM, and comprehensive user authentication features.
    *   **Frontend**: **Tailwind CSS + HTMX** — provides a premium, responsive "app-like" experience on mobile touch targets at the gym with zero heavy JS framework overhead.
    *   **Database**: **SQLite** — simple, file-based database ideal for private self-hosted projects.
    *   **Server**: **Gunicorn** — production-grade WSGI HTTP server to execute Django.
    *   **Reverse Proxy**: **Caddy** — selected over Nginx for its incredibly clean configuration syntax and automatic TLS management.
2.  **Containerizing the App**:
    A containerized structure was built using three primary configuration files:
    *   `requirements.txt`: Specified Python packages (`Django`, `gunicorn`).
    *   `Dockerfile`: Built the Python 3.11 environment.
    *   `docker-compose.yml`: Defined the `web` container (running Gunicorn) and the `caddy` container (handling SSL/routing).

---

## 🕵️ The Debugging Chronicles: Fascinating Issues & Technical Solutions

During development, several complex bugs and interesting environment issues arose. Below are their post-mortems and resolutions.

### 1. The `DisallowedHost` Block
> [!IMPORTANT]
> **Symptom**: When attempting to access the admin panel via the server's local LAN IP address (`http://192.168.50.70:666/admin`), Django threw a `DisallowedHost` crash.
*   **Root Cause**: This is a core Django security feature. It blocks HTTP Host header attacks by ignoring incoming requests that don't match the domains or IPs explicitly permitted in the settings.
*   **The Secure Fix**: Instead of setting `ALLOWED_HOSTS = ['*']` (which opens the app to host header spoofing), the configuration was locked down to only accept the specific network interfaces:
    ```python
    # config/settings.py
    ALLOWED_HOSTS = ['192.168.50.70', '100.103.46.112', 'localhost', '127.0.0.1']
    ```

### 2. The Login Profile Race Condition
> [!WARNING]
> **Symptom**: After setting up a superuser and logging into `/admin/login/`, the app crashed with `RelatedObjectDoesNotExist: User has no lifterprofile`.
*   **Root Cause**: A Django database signal (`post_save` listener) was added to automatically generate a `LifterProfile` whenever a user was saved. However, the superuser had been created *before* the signal code was written. When that superuser logged in, Django updated the `last_login` timestamp, triggering the `post_save` signal. The signal aggressively tried to save the profile (`instance.lifterprofile.save()`), but since none existed yet, it crashed.
*   **The Secure Fix**: Implement defensive try/except handling within the receiver signal:
    ```python
    # lifting/models.py
    @receiver(post_save, sender=User)
    def save_or_create_user_profile(sender, instance, created, **kwargs):
        if created:
            LifterProfile.objects.create(user=instance)
        else:
            try:
                instance.lifterprofile.save()
            except LifterProfile.DoesNotExist:
                LifterProfile.objects.create(user=instance) # Catch and create on-the-fly safely
    ```

### 3. The Port `666` Mystery ("The Devil's Port")
> [!CAUTION]
> **Symptom**: The developer originally ran the app on port `666` as a theme for moving heavy iron, but encountered repeated browser connection refuels and `502 Bad Gateway` errors during container reloads.
*   **Technical Breakdown**:
    1.  **Browser Port Blocking**: Most modern browsers (Chrome, Safari, Firefox) hard-block port `666` with an `ERR_UNSAFE_PORT` warning. This port is historically reserved for Doom/Trojan exploits and is blacklisted out of security precaution.
    2.  **Port Mapping Misalignment**: Caddy was configured to route requests via `reverse_proxy web:8000`. However, Gunicorn was instructed to bind to `0.0.0.0:666`. Since Gunicorn was listening on door `666` but Caddy was knocking on door `8000`, Caddy failed to reach Gunicorn and raised a `502 Bad Gateway`.
*   **The Fix**: Keep Gunicorn and Caddy talking on the standard internal container port `8000` (`web:8000`), allowing Caddy to expose standard port `80`/`443` externally.

### 4. The HTMX Deletion Button Bug
> [!NOTE]
> **Symptom**: Clicking the dynamic delete button (`X`) on a workout set showed the confirmation pop-up modal, but the set did not get removed from the page or database.
*   **Root Cause**: The HTML originally sent an HTMX `hx-delete` request. Many web servers, firewalls, and CSRF middlewares block or mishandle raw `DELETE` requests unless specialized headers are present.
*   **The Fix**: Converted the HTMX deletion trigger to a standard `POST` request, secured with a CSRF token:
    ```html
    <!-- lifting/templates/lifting/partials/set_row.html -->
    <button hx-post="{% url 'delete_set' set.id %}"
            hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'
            hx-target="closest tr"
            hx-swap="outerHTML"
            class="text-red-500 hover:text-red-700">
        ✕
    </button>
    ```

---

## 🛡️ DevOps & Branch Management Strategy

Managing a staging environment and a production environment on the same Linux host can lead to massive merge conflicts. This section details how Git was customized to make deployment stress-free.

### The Git Configuration Nightmare
Staging requires `Caddyfile.local` and `docker-compose.override.yml` to route to port `8080` (HTTP). Production requires the standard `Caddyfile` and `docker-compose.yml` configured for port `80`/`443` (HTTPS via Tailscale).
Normally, merging `staging` into `production` would overwrite these files, bringing down the server or requiring a tedious `git checkout HEAD <files>` dance.

### The Solution: Automated Git Merge Shielding
A custom git merge driver was configured on the Mac to automatically protect production files:

1.  **Define the custom merge driver** (runs once on the dev machine):
    ```bash
    git config merge.ours.driver true
    ```
2.  **Assign the shield** via a special `.gitattributes` file in the project root:
    ```plaintext
    Caddyfile merge=ours
    docker-compose.yml merge=ours
    ```
3.  **How it works**:
    During a merge, Git detects the `.gitattributes` directive. Instead of attempting to merge text or throwing a merge conflict, it silently keeps the target branch's copy of `Caddyfile` and `docker-compose.yml` completely untouched!

---

## 🧪 Comprehensive Test Suite & Security Auditing

A premium developer experience requires bulletproof tests. PrivateLift implements three tiers of tests:

### 1. View & Interaction Tests (`LogSetViewTests`, `DashboardViewTests`, `AnalyticsViewTests`)
*   Tests the dynamic HTMX response headers (`HX-Trigger: setLogged`).
*   Verifies fallback mechanisms when invalid input (e.g. text instead of integers) is supplied.
*   Ensures users cannot access others' metrics (cross-user data isolation checks).

### 2. Boundary & Extreme Value Tests (`BoundaryLimitTests`)
*   Asserts proper validation on extreme inputs (e.g., negative weights, decimals in integer fields).
*   Enforces input validation on the 1RM database models.

### 3. Global Security Audit Tests (`GlobalSecurityTests`)
*   Sweeps all views (`dashboard`, `analytics`, `profile_settings`, `export_data`) and strictly asserts that unauthorized anonymous users are met with a `302 Redirect` bouncing them back to the `/accounts/login/` page.

### Running the Test Suite
Tests can be executed in two environments:
```bash
# Option A: The Virtual Environment Way (Native Mac)
python manage.py test

# Option B: The Docker Compose Way
docker compose exec web python manage.py test
```

---

## 📈 Core Mathematical Formulas

The application includes two key lift metrics:
1.  **Epley Formula** (calculated automatically on set save):
    $$\text{e1RM} = \text{weight} \times \left(1 + \frac{\text{reps}}{30}\right)$$
2.  **Working Program Sets**:
    Automatically rounds calculated percentages (e.g., 85% of 1RM) to the nearest $5\text{ lbs/kgs}$ for standard plate loading compatibility:
    ```python
    round((one_rep_max * percentage) / 5) * 5
    ```
