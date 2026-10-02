# job_hunter

Busca todos los días empleos remotos en ~70 fuentes y te manda por email **solo las vacantes nuevas**, ordenadas por puntaje y con un mensaje de presentación listo para copiar. Descarta las que solo aceptan USA/Europa, pagan menos de $12k/año o no encajan con tu perfil.

## Fuentes
- **Portales remotos:** Remotive, RemoteOK, Himalayas (+ búsqueda por término), Jobicy, Arbeitnow, We Work Remotely, Working Nomads, 4 Day Week, Remote First Jobs.
- **LatAm:** Get on Board (búsqueda por término, solo remoto).
- **Comunidad:** Hacker News "Who is hiring", bolsa de python.org.
- **Páginas de empleo de empresas** (Greenhouse, Lever, Ashby): GitLab, Canonical, Mozilla, Supabase, Stripe, Toptal, Wizeline, etc. La lista está en `config.json → companies`; para agregar una empresa, añade el identificador que aparece en su URL de empleos (`boards.greenhouse.io/<id>`, `jobs.lever.co/<id>`, `jobs.ashbyhq.com/<id>`).

LinkedIn, Indeed y Glassdoor no se incluyen: no tienen API pública y prohíben el scraping.

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
- `search_terms`: términos que se buscan en Himalayas y Get on Board.
- `niche_keywords` / `latam_countries`: vacantes de tu nicho (Odoo) en un país LatAm se muestran con aviso aunque `strict_location` esté activo.
- `pitch`: tu mensaje base; `{company}` y `{title}` se rellenan solos.

`python3 job_hunter.py --all` vuelve a mostrar también las ya vistas.
