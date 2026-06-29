"""
Crypto Trading Bot - Telegram Mini App
======================================
Installa le dipendenze con:
    pip install python-telegram-bot requests

Poi configura i 3 valori qui sotto e avvia con:
    python bot.py
"""

import asyncio
import logging
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, MenuButtonWebApp
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ============================================================
#  CONFIGURA QUESTI 3 VALORI PRIMA DI AVVIARE
# ============================================================
BOT_TOKEN = "IL_TUO_TOKEN_DA_BOTFATHER"          # es. 7812345678:AAH...
CHAT_ID   = "IL_TUO_CHAT_ID"                     # trova con @userinfobot
APP_URL   = "https://TUO-USERNAME.github.io/crypto-bot-miniapp/"
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Coppie da monitorare (CoinGecko IDs)
COINS = {
    "bitcoin":  "BTC",
    "ethereum": "ETH",
    "solana":   "SOL",
    "binancecoin": "BNB",
    "ripple":   "XRP",
}

# ------------------------------------------------------------------
# Calcolo RSI semplificato
# ------------------------------------------------------------------
def calcola_rsi(prezzi: list, periodo: int = 14) -> float:
    if len(prezzi) < periodo + 1:
        return 50.0
    delta = [prezzi[i] - prezzi[i-1] for i in range(1, len(prezzi))]
    guad = [max(d, 0) for d in delta[-periodo:]]
    perd = [max(-d, 0) for d in delta[-periodo:]]
    ag = sum(guad) / periodo
    ap = sum(perd) / periodo
    if ap == 0:
        return 100.0
    rs = ag / ap
    return round(100 - (100 / (1 + rs)), 1)

# ------------------------------------------------------------------
# Fetch prezzi live da CoinGecko (API gratuita, no chiave)
# ------------------------------------------------------------------
def fetch_prezzi() -> dict:
    ids = ",".join(COINS.keys())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=eur&include_24hr_change=true"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Errore fetch prezzi: {e}")
        return {}

# ------------------------------------------------------------------
# Fetch storico prezzi per RSI (ultimi 15 giorni)
# ------------------------------------------------------------------
def fetch_storico(coin_id: str) -> list:
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=eur&days=15"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return [p[1] for p in data.get("prices", [])]
    except Exception as e:
        logger.error(f"Errore storico {coin_id}: {e}")
        return []

# ------------------------------------------------------------------
# Genera segnale di trading
# ------------------------------------------------------------------
def genera_segnale(rsi: float, change_24h: float) -> tuple:
    if rsi < 30:
        return "🟢 BUY", "RSI in ipervenduto — possibile rimbalzo"
    elif rsi > 70:
        return "🔴 SELL", "RSI in ipercomprato — possibile correzione"
    elif change_24h > 5:
        return "🟡 ATTENZIONE", "Salita rapida nelle ultime 24h"
    elif change_24h < -5:
        return "🟡 ATTENZIONE", "Calo forte nelle ultime 24h"
    else:
        return "⏸ HOLD", "Nessun segnale forte"

# ------------------------------------------------------------------
# Costruisce il messaggio di analisi
# ------------------------------------------------------------------
def build_analisi() -> str:
    prezzi = fetch_prezzi()
    if not prezzi:
        return "⚠️ Impossibile recuperare i dati. Riprova tra poco."

    righe = ["📊 *Analisi Crypto in tempo reale*\n"]
    segnali_forti = []

    for coin_id, simbolo in COINS.items():
        dati = prezzi.get(coin_id, {})
        prezzo = dati.get("eur", 0)
        change = dati.get("eur_24h_change", 0)

        storico = fetch_storico(coin_id)
        rsi = calcola_rsi(storico) if storico else 50.0

        segnale, motivo = genera_segnale(rsi, change)
        variazione = f"+{change:.1f}%" if change >= 0 else f"{change:.1f}%"

        riga = (
            f"*{simbolo}* @ €{prezzo:,.2f}\n"
            f"  24h: {variazione} | RSI: {rsi}\n"
            f"  {segnale} — {motivo}"
        )
        righe.append(riga)

        if "BUY" in segnale or "SELL" in segnale:
            segnali_forti.append(f"{simbolo}: {segnale}")

    righe.append(f"\n⏰ Aggiornato: {datetime.now().strftime('%H:%M:%S')}")
    if segnali_forti:
        righe.append("\n🚨 *Segnali attivi:* " + " | ".join(segnali_forti))

    return "\n\n".join(righe)

# ------------------------------------------------------------------
# HANDLER /start  →  apre la Mini App
# ------------------------------------------------------------------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    nome = user.first_name if user else "trader"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "💰 Apri Dashboard",
            web_app=WebAppInfo(url=APP_URL)
        )
    ]])

    testo = (
        f"👋 Ciao *{nome}*\\!\n\n"
        f"🤖 Il tuo bot di trading crypto è *attivo*\\.\n\n"
        f"📱 Clicca il pulsante per aprire la dashboard completa, "
        f"oppure usa /analisi per ricevere i segnali qui in chat\\.\n\n"
        f"💡 Con *€5 di capitale* ti consiglio la strategia DCA Smart\\."
    )

    await update.message.reply_text(testo, parse_mode="MarkdownV2", reply_markup=keyboard)

# ------------------------------------------------------------------
# HANDLER /analisi  →  analisi immediata
# ------------------------------------------------------------------
async def analisi(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Analizzando il mercato, attendi...")
    msg = build_analisi()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Dashboard completa", web_app=WebAppInfo(url=APP_URL))
    ]])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

# ------------------------------------------------------------------
# HANDLER /aiuto
# ------------------------------------------------------------------
async def aiuto(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    testo = (
        "📚 *Comandi disponibili:*\n\n"
        "/start — Apri la dashboard\n"
        "/analisi — Segnali di trading ora\n"
        "/aiuto — Questa guida\n\n"
        "La dashboard riceve aggiornamenti automatici ogni ora."
    )
    await update.message.reply_text(testo, parse_mode="Markdown")

# ------------------------------------------------------------------
# JOB: notifica automatica ogni ora
# ------------------------------------------------------------------
async def notifica_oraria(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Invio analisi oraria...")
    msg = build_analisi()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Apri Dashboard", web_app=WebAppInfo(url=APP_URL))
    ]])
    await ctx.bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ------------------------------------------------------------------
# JOB: riassunto giornaliero
# ------------------------------------------------------------------
async def riassunto_giornaliero(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    prezzi = fetch_prezzi()
    if not prezzi:
        return

    testo = "📈 *Riassunto giornaliero*\n\n"
    for coin_id, simbolo in COINS.items():
        d = prezzi.get(coin_id, {})
        prezzo = d.get("eur", 0)
        change = d.get("eur_24h_change", 0)
        emoji = "📈" if change > 0 else "📉"
        testo += f"{emoji} *{simbolo}*: €{prezzo:,.2f} ({change:+.1f}%)\n"

    testo += f"\n⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Apri Dashboard", web_app=WebAppInfo(url=APP_URL))
    ]])
    await ctx.bot.send_message(
        chat_id=CHAT_ID,
        text=testo,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ------------------------------------------------------------------
# Handler WebApp data (dati inviati dalla mini app)
# ------------------------------------------------------------------
async def webapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = update.effective_message.web_app_data.data
    await update.message.reply_text(f"📲 Dati dalla Mini App ricevuti:\n`{data}`", parse_mode="Markdown")

# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main() -> None:
    print("=" * 50)
    print("🤖 Crypto Trading Bot avviato!")
    print(f"📱 Mini App: {APP_URL}")
    print("=" * 50)
    print("Vai su Telegram, cerca il tuo bot e clicca /start")
    print("Premi Ctrl+C per fermare.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analisi", analisi))
    app.add_handler(CommandHandler("aiuto", aiuto))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data))

    # Jobs schedulati
    job_queue = app.job_queue
    job_queue.run_repeating(notifica_oraria, interval=3600, first=60)        # ogni ora
    job_queue.run_daily(riassunto_giornaliero, time=datetime.strptime("20:00", "%H:%M").time())  # ogni giorno

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
