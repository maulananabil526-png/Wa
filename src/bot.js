import fs from 'fs'
import path from 'path'
import { Telegraf } from 'telegraf'

import { BOT_TOKEN } from './config.js'
import start from './commands/start.js'
import pairing from './commands/pairing.js'
import cekbio from './commands/cekbio.js'
import { startSocket } from './whatsapp.js'

if (!BOT_TOKEN) {
  console.error('❌ BOT_TOKEN belum di set')
  process.exit(1)
}

const bot = new Telegraf(BOT_TOKEN)

/* ========== COMMANDS ========== */
start(bot)
pairing(bot)
cekbio(bot)
/* ========== LAUNCH BOT ========== */
bot.launch({
  dropPendingUpdates: true
})
console.log('🤖 Telegram bot berjalan')

/* ========== RESTORE WA SESSION ========== */
const SESSIONS_DIR = path.join(process.cwd(), 'sessions')

;(async () => {
  if (fs.existsSync(SESSIONS_DIR)) {
    for (const userId of fs.readdirSync(SESSIONS_DIR)) {
      console.log(`🔁 Restore WhatsApp session: ${userId}`)
      await startSocket(userId)
    }
  }
})()


/* ========== OPTIONAL SHUTDOWN ========== */
// boleh hapus kalau belum perlu
process.once('SIGINT', () => bot.stop('SIGINT'))
process.once('SIGTERM', () => bot.stop('SIGTERM'))


