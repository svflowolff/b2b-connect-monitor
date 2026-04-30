# Slack Reminder-Bot via GitHub Actions

Dieser Bot postet Donnerstag bis Sonntag um 10:00 Europe/Berlin eine Reminder-Nachricht in einen Slack-Channel und pausiert automatisch bis zum nächsten Donnerstag, sobald jemand auf eine der Nachrichten mit einem Emoji reagiert.

Läuft kostenlos in der Cloud auf **GitHub Actions** – kein eigener Server, kein Mac-Standby-Problem.

---

## Was Du brauchst

- Einen Slack-Workspace, in dem Du Apps installieren darfst (Workspace-Admin oder freigegebene Berechtigung)
- Einen GitHub-Account (Free Plan reicht)
- ~30 Minuten Zeit für das einmalige Setup

---

## Architektur

```
┌─────────────────────────┐         ┌─────────────────────────┐
│   Slack-App (Bot-User)  │ ◄────── │    GitHub Actions       │
│   • chat:write          │         │  • Cron Do–So 10:00     │
│   • channels:history    │         │  • Python-Skript        │
│   • reactions:read      │         │  • Secrets für Token    │
└─────────────────────────┘         └─────────────────────────┘
         ▲                                       │
         │ postet, liest Reaktionen              │
         ▼                                       │
┌─────────────────────────┐                      │
│   Dein Slack-Channel    │ ◄────────────────────┘
└─────────────────────────┘
```

Der Trick mit dem Pausieren ist **stateless**: Bei jedem Lauf schaut das Skript selbst in den Channel und prüft, ob seit dem letzten Donnerstag eine Bot-Nachricht eine Reaktion bekommen hat. Kein eigener Speicher nötig – das ist robust gegen ausgefallene Workflow-Läufe.

---

## Schritt 1 – Slack-App anlegen

### 1.1 App erstellen

1. Auf **https://api.slack.com/apps** mit Deinem Workspace einloggen.
2. **„Create New App" → „From scratch"**.
3. **App Name:** z. B. `Reminder Bot`. **Workspace:** auswählen. **Create App**.

### 1.2 Bot-Identität setzen

1. Linke Sidebar → **„App Home"**.
2. Bei „Your App's Presence in Slack" → **Edit** beim Display Name.
3. **Display Name:** `Reminder Bot`, **Default Username:** `reminder-bot`. Speichern.

### 1.3 Scopes setzen

1. Linke Sidebar → **„OAuth & Permissions"**.
2. Bei **„Bot Token Scopes"** (NICHT „User Token Scopes") drei Scopes hinzufügen:
   - `chat:write` – darf Nachrichten posten
   - `channels:history` – liest öffentliche Channel-Historie (für den Reaktions-Check)
   - `reactions:read` – darf Reaktionen sehen

   Wenn der Channel **privat** ist, zusätzlich:
   - `groups:history`

### 1.4 App im Workspace installieren

1. Auf derselben Seite oben **„Install to Workspace"** → **„Allow"**.
2. Du landest wieder auf OAuth & Permissions. Dort steht jetzt das **„Bot User OAuth Token"** – beginnt mit `xoxb-…`.
3. Token in einen Passwortmanager kopieren. Du brauchst ihn gleich.

> **Wichtig:** Falls Du später noch Scopes änderst, musst Du **„Reinstall to Workspace"** klicken, sonst greifen die neuen Scopes nicht.

### 1.5 Bot in den Ziel-Channel einladen

In Slack:

```
/invite @reminder-bot
```

### 1.6 Channel-ID holen

In Slack auf den Channel-Namen oben klicken → ganz unten im Popup steht eine Channel-ID, z. B. `C09ABCDEF12`. Auch diese aufschreiben.

---

## Schritt 2 – GitHub-Repository einrichten

### 2.1 Privates Repo anlegen

1. https://github.com/new
2. **Repository name:** z. B. `slack-reminder-bot`
3. **Visibility:** **Private** (wichtig – wegen der Tokens)
4. „Create repository"

### 2.2 Dateien hochladen

Du brauchst diese drei Dateien aus dem Ordner, der neben dieser README liegt:

```
slack-reminder-bot/
├── reminder.py
├── .gitignore
└── .github/
    └── workflows/
        └── reminder.yml
```

**Variante A – einfach per Browser:**

1. Im neuen Repo → **„Add file" → „Upload files"**
2. `reminder.py` und `.gitignore` einfach reinziehen
3. Für die YAML: Im Repo **„Add file" → „Create new file"** → als Dateinamen `.github/workflows/reminder.yml` eingeben (GitHub erkennt das `/` und legt die Ordner an) → Inhalt aus der lokalen Datei kopieren → Commit.

**Variante B – per Git-CLI:**

```bash
cd /Users/florianwolff/Documents/Claude/Projects/persönliche\ Asana\ Assistent*in/slack-reminder-bot
git init
git add .
git commit -m "Initial commit – Slack reminder bot"
git branch -M main
git remote add origin https://github.com/<dein-user>/slack-reminder-bot.git
git push -u origin main
```

### 2.3 Secrets und Variables hinterlegen

Im Repo → **Settings → Secrets and variables → Actions**.

**Tab „Secrets" → „New repository secret":**

| Name | Wert |
|---|---|
| `SLACK_BOT_TOKEN` | Dein `xoxb-…` Token aus Schritt 1.4 |
| `SLACK_CHANNEL_ID` | Channel-ID aus Schritt 1.6, z. B. `C09ABCDEF12` |

**Tab „Variables" → „New repository variable":**

| Name | Wert |
|---|---|
| `REMINDER_TOPIC` | Worum geht's? z. B. `Wochenreport bei Asana abgeben` |

Den `REMINDER_TOPIC` packen wir bewusst in „Variables" und nicht in „Secrets", weil's keine geheime Info ist und Du ihn dann auch ohne Re-Edit in den Logs sehen kannst.

---

## Schritt 3 – Testen

1. Im Repo zum Tab **„Actions"** wechseln.
2. Links **„Slack Daily Reminder"** auswählen.
3. Rechts **„Run workflow"** → **„Run workflow"** klicken.

Was sollte passieren:

- Wenn aktuell **kein** Send-Tag ist (also Mo–Mi) oder die Berliner Stunde nicht 10 ist: Der Workflow läuft durch und loggt „Skip". Das ist erwartet – das Skript ist defensiv.
- Wenn Du das Skript zum Testen wirklich senden lassen willst, kannst Du temporär in `reminder.py` die Wochentag- und Stundenchecks auskommentieren (die beiden `if … return 0`-Blöcke ganz oben in `main()`), commiten, manuell triggern, und danach wieder reaktivieren.

Im Logs-Output siehst Du genau, was der Bot getan hat (`Bestätigung gefunden`, `Tag X gesendet`, etc.).

---

## Schritt 4 – Reaktion testen

1. Nach erfolgreichem Send: in Slack auf die Bot-Nachricht reagieren (irgendein Emoji).
2. Workflow erneut manuell triggern.
3. Im Log sollte stehen: `[reminder] Bestätigung gefunden – heute keine Nachricht.`

---

## Reminder-Texte anpassen

Die vier Tagestexte stehen oben in `reminder.py` im Dictionary `MESSAGES`. Tag 1 = Donnerstag, Tag 4 = Sonntag. Der Platzhalter `{topic}` wird durch den `REMINDER_TOPIC` aus den Repo-Variables ersetzt.

Wenn Du die Texte änderst:

```bash
# Änderung commiten
git add reminder.py
git commit -m "Reminder-Texte angepasst"
git push
```

Beim nächsten Cron-Lauf greifen die neuen Texte automatisch.

---

## Wann läuft der Cron?

Der Workflow definiert zwei Cron-Trigger (8:00 und 9:00 UTC), damit es Sommer- wie Winterzeit-sicher 10:00 Europe/Berlin trifft. Das Skript akzeptiert dann nur den Lauf, bei dem die Berliner Stunde wirklich 10 ist – der andere wird verworfen.

> **Realistisch zur Genauigkeit:** GitHub Actions garantiert keine sekundengenaue Ausführung. Bei hoher Plattform-Last kann sich der Cron um 5–15 Minuten verzögern, in seltenen Fällen mehr. Für einen täglichen Reminder ist das egal.

---

## Kostenrechnung

GitHub Free Plan: 2.000 Workflow-Minuten pro Monat für private Repos. Dieser Workflow braucht ~30 Sekunden pro Lauf und feuert maximal 8× pro Woche (zwei Crons × vier Tage) ≈ 32× pro Monat → ~16 Minuten/Monat. Damit bleibst Du **dauerhaft im Free Tier**.

---

## Troubleshooting

**„not_in_channel" Fehler im Log:**
Bot wurde nicht in den Channel eingeladen. → `/invite @reminder-bot`.

**„missing_scope" Fehler:**
Scope vergessen oder Reinstall vergessen. Zurück zu OAuth & Permissions, Scope hinzufügen, **Reinstall to Workspace** klicken.

**„invalid_auth" Fehler:**
Token in `SLACK_BOT_TOKEN` ist falsch oder wurde rotiert. Token neu kopieren, Secret aktualisieren.

**Workflow läuft, aber sendet nie etwas:**
Das ist meistens richtig – das Skript skipt an Mo–Mi, außerhalb der 10-Uhr-Stunde, oder wenn schon eine Reaktion da ist. Ins Log schauen, da steht der genaue Skip-Grund.

**Cron läuft gar nicht:**
GitHub deaktiviert Scheduled Workflows in inaktiven Repos automatisch nach ~60 Tagen. Lösung: gelegentlich einen Commit pushen (z. B. ein Datum in dieser README ändern) oder einmal pro Monat manuell triggern.

**Alle Nachrichten kommen plötzlich, obwohl jemand reagiert hat:**
Möglich, dass der Marker-String `🔔 [Daily-Reminder]` im Skript geändert wurde, aber alte Bot-Nachrichten ihn noch enthalten. Marker ist die Erkennungs-Signatur – ändert sich der, findet das Skript die alten Nachrichten nicht mehr und der Reaktions-Check läuft ins Leere.

---

## Erweiterungs-Ideen für später

- **Bestätigungs-DM an Dich:** Wenn der Bot eine Reaktion erkennt, könnte er Dir privat Bescheid geben. Dafür im Skript bei `has_reaction == True` ein zusätzliches `chat.postMessage` an Deine User-ID.
- **Mehrere Channels parallel:** `SLACK_CHANNEL_ID` zu einer Liste machen und im Skript darüber loopen.
- **Asana-Integration:** Falls die Erinnerung an einen Asana-Task hängt, kann der Bot beim Eintreffen einer Reaktion den Task auch direkt schließen. Sag mir Bescheid – kann ich dazubauen.
- **Statistik:** Pro Woche tracken, an welchem Tag die Bestätigung kam. Nach ein paar Wochen siehst Du, ob das Team eher Do oder So aktiv wird.

---

## Was als Nächstes?

Sobald Du die Slack-App aufgesetzt hast und das Repo angelegt ist, ping mich. Ich kann Dir dann beim Test-Run helfen, die Reminder-Texte auf Dein konkretes Thema feintunen oder bei Erweiterungen unterstützen. 🚀
