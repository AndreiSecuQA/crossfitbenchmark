# Muscle Benchmark Bot

Telegram bot pentru urmărirea progresului CrossFit în grup. Colectează date despre exerciții, calculează scoruri relative la greutatea corporală și afișează clasamente.

## Setup local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Editează .env cu token-ul botului și DATABASE_URL

python -m bot.main
```

## Variabile de mediu

| Variabilă | Descriere |
|---|---|
| `BOT_TOKEN` | Token-ul botului de la @BotFather |
| `DATABASE_URL` | URL PostgreSQL (format asyncpg) |
| `FIRST_ADMIN_ID` | Telegram ID-ul primului admin |

## Deploy pe Railway

1. Creează un proiect nou pe Railway
2. Adaugă un serviciu PostgreSQL
3. Conectează repo-ul GitHub
4. Setează variabilele de mediu
5. Railway folosește `Procfile` pentru a porni botul

`DATABASE_URL` pe Railway va fi format `postgresql://...` — înlocuiește cu `postgresql+asyncpg://...`

## Comenzi bot

| Comandă | Descriere |
|---|---|
| `/start` | Crează profil (înălțime, greutate, limbă) |
| `/session` | Completează sesiunea curentă |
| `/stats` | Statisticile tale |
| `/leaderboard` | Clasament general + per exercițiu |
| `/weight <kg>` | Actualizează greutatea |
| `/help` | Lista comenzilor |

### Admin
| Comandă | Descriere |
|---|---|
| `/trigger` | Declanșează o sesiune nouă pentru toți |
| `/addadmin <id>` | Adaugă un admin |
| `/removeadmin <id>` | Elimină un admin |
| `/listadmins` | Lista adminilor |
| `/listusers` | Lista utilizatorilor |

## Exerciții urmărite

- Pull-ups (repetări)
- Push-ups (repetări)
- Dips (repetări)
- Sit-ups (repetări)
- Plank (secunde)
- Leg raises (repetări)
- Alergare (distanță + timp)
- Burpees (repetări)
- Sărituri la coardă (repetări)
- Squats (repetări)
- Lunges (repetări)
- Box jumps (repetări)

## Scoring

Scorul fiecărui exercițiu este normalizat la 0-100. Pentru exercițiile de forță (pull-ups, dips, push-ups) se aplică un factor de greutate corporală (allometric scaling `weight^0.67`) care avantajează atleții mai grei.

Scorul global = media aritmetică a scorurilor individuale.
