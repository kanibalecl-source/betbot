# Etap 6 - Jedna paczka lokalna + gotowa do serwera

Ta paczka zawiera wszystkie dotychczasowe etapy w jednej wersji:

- czysta struktura po Etapie 1,
- audytowo uporzadkowana architektura Etapu 3,
- append-only historia,
- upgrade zakladek Etapu 4,
- wyglad WWW Etapu 5.

## Najwazniejsza gwarancja

Uruchomienie lokalne na laptopie **nie zmienia bota na serwerze**.

Dlaczego:

- lokalny start uzywa `app_launcher_local.py`, a nie Railway,
- lokalny scheduler uzywa `scheduler_engine_local.py`,
- dashboard startuje na `127.0.0.1`,
- wszystkie pliki historii i bazy zapisuja sie lokalnie w folderze tej paczki,
- paczka nie zawiera `.env` ani danych produkcyjnych z serwera,
- jedyne polaczenia zewnetrzne to API, ktore sam wpiszesz w `.env.local`.

## Czego potrzebujesz

1. Windows z Python 3.11 lub nowszym.
2. Klucz `API_FOOTBALL_KEY`.
3. Opcjonalnie `ODDS_API_KEY`.
4. Opcjonalnie `OPENAI_API_KEY` do GPT.

Bez kluczy API dashboard moze sie otworzyc, ale bot nie pobierze prawdziwych meczow i GPT nie wykona analizy.

## Test lokalny krok po kroku

### 1. Rozpakuj ZIP

Rozpakuj paczke Etapu 6 do osobnego folderu, na przyklad:

```text
C:\Users\MSI\Desktop\betbot-test-local
```

Nie rozpakowuj jej do folderu produkcyjnego serwera.

### 2. Zainstaluj zaleznosci lokalnie

Kliknij:

```text
INSTALL_LOCAL_WINDOWS.bat
```

Skrypt utworzy lokalny folder `.venv` i zainstaluje biblioteki z `requirements.txt`.

### 3. Przygotuj lokalne klucze

Skopiuj:

```text
.env.local.example
```

jako:

```text
.env.local
```

Wpisz swoje klucze:

```text
API_FOOTBALL_KEY=...
ODDS_API_KEY=...
OPENAI_API_KEY=...
LOCAL_PORT=8501
```

To jest plik lokalny. Nie jest potrzebny na serwerze.

### 4. Uruchom pelnego bota lokalnie

Kliknij:

```text
START_LOCAL_FULL.bat
```

Uruchomi to lokalnie:

- scheduler,
- prematch bot,
- live pipeline,
- settlement,
- persistence,
- retraining,
- dashboard Streamlit.

### 5. Otworz panel

Wejdz w przegladarce:

```text
http://127.0.0.1:8501
```

Jesli zmieniles `LOCAL_PORT`, uzyj swojego portu.

### 6. Co sprawdzic przed wgraniem na serwer

Sprawdz zakladki:

- LIVE,
- PREMATCH,
- AI,
- ANALYTICS,
- HISTORY,
- MOJE ZAKLADY,
- RANKING,
- GPT CHAT.

Sprawdz logi w oknie terminala:

```text
BETBOT LOCAL APP LAUNCHER START
LOCAL SCHEDULER FILE STARTED
BOT EXECUTED
PERSISTENCE/HISTORY OK
LOCAL HEARTBEAT
```

Sprawdz lokalne pliki:

```text
data\auto_all_picks.csv
data\history\
data\kanibal_persistent.sqlite3
```

Jesli te pliki powstaja lokalnie, to znaczy, ze lokalny zapis dziala.

## Start samego panelu

Jesli chcesz zobaczyc tylko WWW bez schedulerow, kliknij:

```text
START_LOCAL_DASHBOARD_ONLY.bat
```

## Jak upewnic sie, ze serwer nie zostal ruszony

Podczas testu lokalnego:

- nie logujesz sie do Railway,
- nie robisz redeploy,
- nie wgrywasz plikow na serwer,
- nie kasujesz zadnego volume `/data`,
- wszystkie nowe pliki powstaja w lokalnym folderze paczki.

To jest fizycznie odseparowane od serwera.

## Wdrozenie na serwer dopiero po tescie

Dopiero gdy lokalnie wszystko dziala:

1. Zrob backup aktualnej wersji z serwera.
2. Wgraj paczke Etapu 6 na serwer.
3. Nie usuwaj katalogu `/data` na serwerze.
4. Zrob redeploy.
5. Sprawdz logi i panel.

## Cofniecie

Jesli po wdrozeniu na serwer cos bedzie nie tak, wgraj poprzedni backup ZIP i zrob redeploy.

