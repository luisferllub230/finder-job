# job_hunter

Busca todos los días empleos remotos en Remotive, RemoteOK, Himalayas, Jobicy, Arbeitnow, We Work Remotely y "Who is hiring" de Hacker News. Descarta los que solo aceptan USA/Europa, los de menos de $12k/año y los que no encajan con tu perfil. Genera `reports/jobs_FECHA.html` con **solo vacantes nuevas**, ordenadas por puntaje y con un mensaje de presentación listo para copiar.

## Instalación (WSL / Linux / macOS)
```bash
cd ~/repos/finder-job
python3 job_hunter.py --no-email           # primera corrida de prueba
```
No necesita `pip install`.

## Cómo corre (GitHub Actions, 24/7, gratis)
Repo privado `luisferllub230/finder-job`. El workflow `.github/workflows/daily.yml` corre todos los días a las 07:45 (hora RD), envía el reporte a alejandroferllub@gmail.com y guarda `jobs.db` en el repo para no repetir vacantes. No depende de que tu PC esté encendida.

- Correr a mano: `gh workflow run daily-job-hunt` o pestaña **Actions → Run workflow**.
- Ver ejecuciones: `gh run list`.
- Secrets necesarios: `SMTP_USER` (tu Gmail) y `SMTP_PASS` (contraseña de aplicación de Google: myaccount.google.com/apppasswords, requiere 2FA).
- Si una corrida falla, GitHub te avisa por correo.

## Correr en local (opcional)
Crea `.env` (con `chmod 600 .env`):
```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=alejandroferllub@gmail.com
export SMTP_PASS=xxxx_xxxx_xxxx_xxxx
```
Luego `. ./.env && python3 job_hunter.py`. Ojo: en local se crea otro `jobs.db` distinto al del repo.

## Ajustes (config.json)
- `min_annual_usd`: piso salarial (12000 = $1,000/mes).
- `keywords`: peso de cada palabra en el puntaje (Odoo pesa más a propósito).
- `location_ok` / `location_blocked`: qué ubicaciones aceptar o descartar.
- `strict_location`: si es `true`, descarta ubicaciones concretas (ciudad/país) que no estén en `location_ok`. `location_generic` ("remote", etc.) se mantiene con aviso "verificar".
- `exclude_title`: roles a ignorar.
- `pitch`: tu mensaje base; `{company}` y `{title}` se rellenan solos.

`python3 job_hunter.py --all` vuelve a mostrar también las ya vistas.
