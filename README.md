# SportConnect

Webová aplikácia na tipovanie futbalových výsledkov v komunitách priateľov
(predmet Web Design Technology and Methodology, FMFI UK, 2026).

Tím: Peter Duška, Radoslav Dujava, Matúš Nemčík

## Technológie

| Časť | Technológia |
|---|---|
| Backend | Python 3.12+, Django 5.2 |
| Frontend | HTML (Django šablóny), CSS, trochu JavaScriptu (bez frameworku) |
| Databáza | SQLite pri vývoji, PostgreSQL na serveri |
| Zápasy a výsledky | [football-data.org](https://www.football-data.org) API v4 (bezplatný plán) |

## Spustenie u seba

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # a doplň FOOTBALL_DATA_TOKEN
python manage.py migrate
python manage.py sync_matches        # reálne zápasy z football-data.org
python manage.py seed_demo --real    # ukážkové účty, komunita a tipy na reálne zápasy
# bez API kľúča: python manage.py seed_demo  (ukážkové zápasy bez lôg)
python manage.py createsuperuser     # účet do administrácie /admin/
python manage.py runserver
```

Aplikácia beží na http://127.0.0.1:8000. Ukážkové účty (heslo `sportconnect`):
`pavol@example.com`, `tondo@example.com`, `marek@example.com`, `jana@example.com`, `peter@example.com`.

Testy: `python manage.py test tests`

## Zápasy z API

Kľúč z football-data.org patrí do súboru `.env` (premenná `FOOTBALL_DATA_TOKEN`), nikdy nie do kódu.

- `python manage.py sync_matches` – stiahne výsledky za posledné 3 dni a zápasy na 14 dní dopredu
  a vyhodnotí ukončené zápasy.
- Ak je kľúč nastavený, aplikácia sa synchronizuje aj sama, keď niekto otvorí zoznam zápasov
  (najviac raz za `FOOTBALL_SYNC_MINUTES`, predvolene 30 minút).
- `python manage.py evaluate_predictions` – vyhodnotí ukončené zápasy, ktorých výsledok sa zadal ručne v administrácii.

Bezplatný plán má limit 10 požiadaviek za minútu, jedna synchronizácia robí jednu požiadavku na každú súťaž
v `FOOTBALL_COMPETITIONS` (predvolene PL, PD, SA, BL1, FL1, CL). Slovenská Niké liga v bezplatnom pláne nie je,
v ukážkových dátach (`seed_demo`) je len pre testovanie.

## Bodovanie (FR4)

- 3 body – presný výsledok
- 1 bod – správny víťaz alebo remíza
- 0 bodov – inak

Tip sa dá zadať a meniť len do začiatku zápasu (FR3).

## Štruktúra projektu

```
accounts/      používatelia (prihlásenie e-mailom), profil, štatistiky (FR1, FR7)
matches/       ligy, tímy, zápasy, tipy, reakcie, vyhodnocovanie, import z API (FR2–FR4)
communities/   komunity, členstvá, pozvánky, rebríčky (FR5, FR6)
templates/     HTML šablóny
static/        CSS a JavaScript
tests/         automatické testy
```

Globálny rebríček je komunita „SportConnect“, do ktorej sa každý používateľ pridá pri registrácii
a môže ju opustiť. Pozvaný e-mail bez účtu sa stane členom komunity hneď po registrácii.

## Zmeny podľa testovania prototypu (1. kolo)

- Filter zápasov je stále viditeľný (lišta sa pri skrolovaní neskrýva): vyhľadávanie tímu + rýchle filtre líg.
- Zápasy sú zoskupené podľa líg s hlavičkami, ktoré zostávajú prilepené pri skrolovaní; obľúbená liga je prvá.
- Po uložení tipu detail zápasu ukazuje „Your prediction 3 : 1 · Saved“ s tlačidlom „Edit tip“
  a v zozname zápasov je pri zápase značka s tipom – netreba prechádzať do My bets.
- Potvrdenie akcií (toast) sa vysunie s animáciou a po chvíli zmizne.
- Súkromie komunity (predvolene súkromná) a pozvanie priateľov sa nastavuje priamo pri jej vytvorení.

## Nasadenie (Render + Neon)

Aplikácia beží na Render (bezplatná webová služba), databáza na Neon (bezplatný PostgreSQL bez expirácie;
bezplatná databáza na Render po 30 dňoch expiruje).

1. Na [neon.tech](https://neon.tech) vytvoriť projekt (región Frankfurt) a skopírovať connection string.
2. Na [render.com](https://render.com): **New → Blueprint**, vybrať tento repozitár a doplniť premenné
   `DATABASE_URL` (z Neonu) a `FOOTBALL_DATA_TOKEN`.
3. Bezplatná služba na Render nemá prístup do Shellu, preto jednorazové príkazy spúšťame z vlastného počítača
   priamo proti databáze na Neone (v priečinku projektu, s aktivovaným `.venv`):
   ```
   export DATABASE_URL="postgresql://...connection string z Neonu..."
   python manage.py migrate
   python manage.py sync_matches
   python manage.py seed_demo --real --password VlastneHeslo
   python manage.py createsuperuser
   unset DATABASE_URL        # späť na lokálnu databázu db.sqlite3
   ```

Bezplatná služba na Render sa po 15 minútach bez návštevy uspí a prvé načítanie potom trvá asi minútu.

Každý push do vetvy `main` na GitHube Render nasadí automaticky; dáta v databáze na Neone pritom zostávajú.
