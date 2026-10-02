# job_hunter

Busca todos los días empleos remotos en Remotive, RemoteOK, Himalayas, Jobicy, Arbeitnow, We Work Remotely y "Who is hiring" de Hacker News. Descarta los que solo aceptan USA/Europa, los de menos de $12k/año y los que no encajan con tu perfil. Genera `reports/jobs_FECHA.html` con **solo vacantes nuevas**, ordenadas por puntaje y con un mensaje de presentación listo para copiar.

## Instalación (WSL / Linux / macOS)
```bash
cd ~/repos/finder-job
python3 job_hunter.py --no-email           # primera corrida de prueba
```
No necesita `pip install`.

## Email diario (opcional, Gmail)
1. Crea una "contraseña de aplicación" en tu cuenta de Google (requiere 2FA).
2. Crea `~/repos/finder-job/.env` y protégelo con `chmod 600 .env`:
```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=alejandroferllub@gmail.com
export SMTP_PASS=xxxx_xxxx_xxxx_xxxx
```

## Programarlo todos los días
**Opción A — Windows Task Scheduler (recomendado si usas WSL, porque cron en WSL no corre si WSL está cerrado):**
Acción → Programa: `wsl.exe`, Argumentos:
```
-e bash -lc "cd ~/repos/finder-job && { [ -f .env ] && . ./.env; }; python3 job_hunter.py >> run.log 2>&1"
```
Disparador: diario 7:45 AM.

**Opción B — cron (Linux/macOS o WSL con `sudo service cron start`):**
```
45 7 * * * cd ~/repos/finder-job && { [ -f .env ] && . ./.env; }; /usr/bin/python3 job_hunter.py >> run.log 2>&1
```

## Ajustes (config.json)
- `min_annual_usd`: piso salarial (12000 = $1,000/mes).
- `keywords`: peso de cada palabra en el puntaje (Odoo pesa más a propósito).
- `location_ok` / `location_blocked`: qué ubicaciones aceptar o descartar.
- `strict_location`: si es `true`, descarta ubicaciones concretas (ciudad/país) que no estén en `location_ok`. `location_generic` ("remote", etc.) se mantiene con aviso "verificar".
- `exclude_title`: roles a ignorar.
- `pitch`: tu mensaje base; `{company}` y `{title}` se rellenan solos.

`python3 job_hunter.py --all` vuelve a mostrar también las ya vistas.
