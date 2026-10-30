# FinMatch (demo frontend)
Run: unzip, then double-click `index.html` (or run `python3 -m http.server` in this folder and open http://localhost:8000).
Internet is needed once for Chart.js and SheetJS (CDN) - used for charts, CSV/Excel upload and export.
Demo logins: user@finmatch.demo / demo123 (or mobile 9876543210), admin@finmatch.demo / admin123.
Files: index.html, css/style.css, js/data.js (demo data + logins), js/i18n.js (Hindi), js/app.js (everything else).
Change the support email default in ADMIN_SUPPORT_EMAIL at the top of js/app.js. To reset demo data, clear localStorage.
Demo only: no real security, no real reconciliation.
