# The PrivateLift Chronicle: How the App Was Built

This document provides a comprehensive, step-by-step developer history and architectural manual for **PrivateLift**. It details how the application was built in dialogue with the Gemini web interface, taking it from a raw set of weightlifting requirements to a fully virtualized, secured, and automated containerized Django application.

---

## Architectural Overview & System Design

PrivateLift is designed to run securely within a **Tailscale virtual private mesh network (Tailnet)**. This completely eliminates the need to expose ports on a home router (no public port forwarding), providing absolute privacy while making the app easily accessible at the gym from a phone.

### Network & Deployment Topology

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

### Environment Configuration Strategy
The application manages local sandbox development and production environments elegantly through Git attributes and Docker overrides:
*   **Local Development (Mac Sandbox)**: Runs on port `8080` (HTTP) mapped to container port `80`, using `Caddyfile.local` (dumbed-down configuration) and `docker-compose.override.yml`. This keeps local git status clean and avoids macOS port `80` permission restrictions.
*   **Production Environment (Server)**: Runs on ports `80` and `443` (with internal Tailscale TLS certificates), reverse proxying directly to Gunicorn on port `8000`.

---

## Step-by-Step Build Phases

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

## The Debugging Chronicles: Fascinating Issues & Technical Solutions

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

### 5. The Containerized Database Migration Gap
> [!IMPORTANT]
> **Symptom**: After deploying new updates to production, attempting to log in crashed with `OperationalError: no such column: lifting_lifterprofile.body_weight`.
*   **Root Cause**: Logging in updates the user's `last_login` field, which fires a `post_save` signal that invokes `instance.lifterprofile.save()`. Because the production SQLite database had not been updated to match the new `LifterProfile` fields (`body_weight`, `gender`, `formula_preference`), the SQL update query failed. Running `python manage.py migrate` directly on the host machine failed due to a missing Python Django environment.
*   **The Fix**: Applied the migrations directly inside the active web container on the host server:
    ```bash
    docker exec -t powerlifting_app_prod-web-1 python manage.py migrate
    ```

---

## DevOps & Branch Management Strategy

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
    During a merge, Git detects the `.gitattributes` directive. Instead of attempting to merge text or throwing a merge conflict, it silently keeps the target branch's copy of `Caddyfile` and `docker-compose.yml` completely untouched.

---

## Security Hardening & Repository Auditing

To secure the repository for sharing on GitHub, we executed a rigorous repository cleanup and security hardening phase:

### 1. Untracking OS Clutter & Local Backups
We removed pre-existing system and backup files from Git tracking:
*   Removed `.DS_Store` (macOS folder configuration).
*   Removed template backups (`base.html.bak` and `dashboard.html.bak`).

### 2. Comprehensive Gitignore Protection
We overhauled the local `.gitignore` to permanently exclude OS files, IDE profiles, virtual environments, tooling outputs, and backups:
```plaintext
# Environment files
.env
db.sqlite3

# Python cache
__pycache__/
*.pyc

# Virtual environments
venv/
.venv/

# OS-specific clutter
.DS_Store
Screenshot*
```

---

## Advanced Metrics & Sports Science Mathematics

We upgraded PrivateLift's strength engine to incorporate advanced mathematical scaling and multi-formula preferences:

### 1. Multi-Formula 1RM Calculators
Instead of relying strictly on Epley, users can select their preferred sports-science equation on the settings page:
*   **Epley:** 
    $$\text{1RM} = \text{Weight} \times \left(1 + \frac{\text{Reps}}{30}\right)$$
*   **Brzycki (Ideal for low-rep ranges):** 
    $$\text{1RM} = \frac{\text{Weight}}{1.0278 - (0.0278 \times \text{Reps})}$$
*   **Lander:** 
    $$\text{1RM} = \frac{100 \times \text{Weight}}{101.3 - (2.6712 \times \text{Reps})}$$

### 2. Relative Strength Scaling (Wilks & DOTS Scoring)
To normalize lifting performance across different weight classes, we added:
*   **Metric Conversion:** Converts imperial inputs (body weight and total lifted) to metric standards.
*   **DOTS Score:** Dynamically applies gendered coefficients against bodyweight.
*   **Wilks Score:** Applies the standard 5th-degree polynomial coefficient.
*   **Gender-Inclusive Math:** To provide dignity and mathematical equity, for users selecting **Non-Binary** or **Other**, the system automatically calculates the lifter's scores using both male and female equations and averages the results.

---

## Gym-Floor UX & Routine Templates

We built premium features to automate workout logging and inter-set rest times:

### 1. Automated Rest Timers
*   **Trigger:** Listens to the HTMX `setLogged` event fired upon a successful set POST.
*   **Visual Layout:** Renders a floating, glassmorphic progress stopwatch at the bottom right.
*   **Features:** Provides adjusters (+1m / -1m), play/pause, reset, and visual pulsing indicators when the clock hits zero.

### 2. Automated Warmup Wizard
*   Calculates a step-by-step checklist based on your target program weight: barbell acclimation (45/135 lbs), nervous activation (55%), muscle preparation (77%), and final single primer (90%).
*   Displays a checkable checklist modal, containing a plate calculator button next to each warmup set for rapid plate mapping.

### 3. Routine Templates & Builder
*   Allows users to load routine templates or save their current daily session as a new routine template.
*   **Auto-Seeding:** If a user profile has no routines, the seeder dynamically populates seven popular templates customized to their exact current strength levels:
    1.  *Powerlifting Big Three* (Squat, Bench, Deadlift working sets)
    2.  *Squat Focus (3x5)*
    3.  *Bench Press Volume (3x5)*
    4.  *Wendler 5/3/1 (5s Week)* (Pyramid scaling at 65%, 75%, and 85%)
    5.  *Texas Method Volume Day* (5x5 Squat and Bench @ 75%)
    6.  *Smolov Jr. (6x6 Squat)* (Specialized volume at 70%)
    7.  *Deload & Active Recovery* (Light active recovery at 50% 1RM)

---

## Comprehensive Test Suite & Security Auditing

PrivateLift implements four tiers of tests:

### 1. View & Interaction Tests
*   `LogSetViewTests`: Verifies dynamic HTMX swaps and `HX-Trigger: setLogged` header dispatching.
*   `DashboardViewTests`: Tests fallback metrics, percentage sliders, and fallback parameters.
*   `AnalyticsViewTests`: Validates tonnage calculations and verifies warmup sets are excluded from totals.

### 2. Routine Template Tests
*   `RoutineTemplateTests`: Validates auto-seeding of the 7 templates on dashboard access, confirms template loads into today's sets, and tests template saving.

### 3. Boundary & Extreme Value Tests
*   Asserts proper validation on extreme inputs (e.g., negative weights, decimals in integer fields, string injections).

### 4. Global Security Audit Tests
*   `GlobalSecurityTests`: Sweeps all primary URLs (including load, save, delete, and import endpoints) and strictly asserts that unauthorized anonymous users are redirected (302) to the `/accounts/login/` page.

### Running the Test Suite
```bash
# Option A: The Virtual Environment Way (Native Mac)
python manage.py test

# Option B: The Docker Compose Way
docker compose exec web python manage.py test
```
