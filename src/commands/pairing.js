import fs from 'fs'
import path from 'path'
import { Markup } from 'telegraf'
import {
  USER_STATE,
  PAIRING_ACTIVE,
  PAIRING_TIMER,
  CHANGE_ACTIVE,
  PAIRING_MSG,
  CEKBIO_MODE
} from '../state.js'

import {
  ensureUserData,
  removeUserData,
  saveUserData
} from './cekbio.js'

import { startSocket, getSession } from '../whatsapp.js'

/* ================= HELPER ================= */

const wait = (ms) => new Promise(r => setTimeout(r, ms))

function resetUser(userId) {
  if (PAIRING_TIMER[userId]) {
    clearInterval(PAIRING_TIMER[userId])
    delete PAIRING_TIMER[userId]
  }
  USER_STATE[userId] = null
  PAIRING_ACTIVE[userId] = false
  CHANGE_ACTIVE[userId] = false
}

function formatUptime(ms) {
  const totalSeconds = Math.floor(ms / 1000)
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = totalSeconds % 60
  return `${h}j ${m}m ${s}d`
}

function formatPairingCode(code) {
  if (!code || code.length < 6) return code
  return `${code.slice(0, 4)}-${code.slice(4)}`
}

function getUptime(userId) {
  const data = CEKBIO_MODE[userId]
  if (!data?.startTime) return 0
  return Date.now() - data.startTime
}
function updateLastOnline(userId) {
  ensureUserData(userId)
  CEKBIO_MODE[userId].lastOnline = Date.now()
  saveUserData(CEKBIO_MODE)
}

function getLastOnline(userId) {
  return CEKBIO_MODE[userId]?.lastOnline || null
}

// ================ SET MODE ================ //
function getCekbioMode(userId) {
  ensureUserData(userId)
  return CEKBIO_MODE[userId].mode
}
function setMode(ctx, mode) {
  const userId = ctx.from.id
  ensureUserData(userId)
  CEKBIO_MODE[userId].mode = mode
  saveUserData(CEKBIO_MODE)

  const menu = renderModeMenu(userId)

  ctx.telegram.editMessageText(
    ctx.chat.id,
    ctx.callbackQuery.message.message_id,
    null,
    menu.text,
    {
      parse_mode: 'Markdown',
      reply_markup: menu.keyboard.reply_markup
    }
  )

  ctx.answerCbQuery(`Mode ${mode.toUpperCase()} aktif`)
}
function renderModeMenu(userId) {
  ensureUserData(userId)
  const current = CEKBIO_MODE[userId].mode

  return {
    text:
`⚙ *Mode Pengecekan*
Pilih kecepatan proses cekbio sesuai kebutuhan kamu.

• *Slow*   → Aman & stabil
• *Medium* → Seimbang (disarankan)
• *Fast*   → Cepat (risiko limit lebih tinggi)

Mode aktif: *${current.toUpperCase()}*`,
    keyboard: Markup.inlineKeyboard([
      [
        Markup.button.callback(
          current === 'slow' ? '🟢 𝚂𝚕𝚘𝚠' : 'Slow',
          'MODE_SLOW'
        ),
        Markup.button.callback(
          current === 'medium' ? '🟢 𝚖𝚎𝚍𝚒𝚞𝚖' : 'Medium',
          'MODE_MEDIUM'
        ),
        Markup.button.callback(
          current === 'fast' ? '🟢 𝚏𝚊𝚜𝚝' : 'Fast',
          'MODE_FAST'
        )
      ],
      [
        Markup.button.callback('「 𝙺𝚎𝚖𝚋𝚊𝚕𝚒 」', 'BACK_TO_DASHBOARD')
      ]
    ])
  }
}

/* ================= DASHBOARD ================= */
function dashboardText(userId) {
  ensureUserData(userId)

  const session = getSession(String(userId))
  const online = !!session?.sock?.user
  const data = CEKBIO_MODE[userId]

  if (!online && !data?.lastSender) {
    return `❌ Sender belum terhubung.

Silakan tambahkan sender untuk mulai menggunakan bot.`
  }

  if (!online && data?.lastSender) {
    const lastText = data.lastOnline
      ? formatUptime(Date.now() -  data.lastOnline) + ' lalu'
      : '-'

    return `╭━━━〔 🔴 SESSION OFFLINE 〕━━━
┃ 👤 User ID : ${userId}
┃   • Last sender : ${data.lastSender}
┃   • Status  : Disconnected
┃   • Last on : ${lastText}
┃   • Mode    : ${data.mode}
╰━━━━━━━━━━━━━━━━━━━━`
  }

  const sender = session.sock.user.id.split(':')[0]
  const uptimeMs = getUptime(userId)

  return `╭━━━〔 🟢 SESSION ACTIVE 〕━━━
┃ 👤 User ID : ${userId}
┃   • Nomor   : ${sender}
┃   • Uptime  : ${formatUptime(uptimeMs)}
┃   • Mode    : ${data.mode}
┃   • Status  : Connected
╰━━━━━━━━━━━━━━━━━━━━`
}

function dashboardKeyboard(userId) {
  const session = getSession(String(userId))
  const online = !!session?.sock?.user
  const data = CEKBIO_MODE[userId]

  if (online) {
    return Markup.inlineKeyboard([
      [
        Markup.button.callback('「 𝙲𝚑𝚊𝚗𝚐𝚎 𝚜𝚎𝚗𝚍𝚎𝚛 」', 'CHANGE_SENDER'),
        Markup.button.callback('「 𝙳𝚒𝚜𝚌𝚘𝚗𝚗𝚎𝚌𝚝 」', 'DISCONNECT')
      ],
      [ Markup.button.callback('「 𝚂𝚎𝚝 𝙼𝚘𝚍𝚎 」', 'CEKBIO_MODE'),]
    ])
  }
  if (data?.lastSender) {
    return Markup.inlineKeyboard([
      [
        Markup.button.callback('「 𝙲𝚘𝚗𝚗𝚎𝚌𝚝 」', 'RECONNECT'),
        Markup.button.callback('「 𝙲𝚑𝚊𝚗𝚐𝚎 𝚜𝚎𝚗𝚍𝚎𝚛 」', 'CHANGE_SENDER')
      ]
    ])
  }
  return Markup.inlineKeyboard([
    [Markup.button.callback('「 𝙰𝚍𝚍 𝚂𝚎𝚗𝚍𝚎𝚛 」', 'ADD_SENDER')]
  ])
}

/* ================= MAIN ================= */

async function startPairing(ctx, userId, number) {
  if (PAIRING_ACTIVE[userId]) return
  try {
    PAIRING_ACTIVE[userId] = true

    const waNumber = number.startsWith('0')
      ? '62' + number.slice(1)
      : number

    if (msgId) {
      await ctx.telegram.editMessageText(
        ctx.chat.id,
        msgId,
        null,
        '⌛ _Memulai proses pairing..._',
        { parse_mode: 'Markdown' }
      )
      PAIRING_MSG[userId] = msgId
    } else {
      const loading = await ctx.reply(
        '⌛ _Memulai proses pairing_....',
        { parse_mode: 'Markdown'}
      )
      PAIRING_MSG[userId] = loading.message_id
    }

    const sock = await startSocket(String(userId))
    sock.ev.on('connection.update', (u) => {
      if (u.connection === 'close') {
        ensureUserData(userId)

        const sender = sock?.user?.id?.split(':')[0] || null
        CEKBIO_MODE[userId].lastOnline = Date.now()
        if (sender) CEKBIO_MODE[userId].lastSender = sender

        saveUserData(CEKBIO_MODE)
      }
    })
    await wait(2000)

    const code = await sock.requestPairingCode(waNumber)
    if (!PAIRING_ACTIVE[userId]) return

    await ctx.telegram.editMessageText(
      ctx.chat.id,
      PAIRING_MSG[userId],
      null,
`🔐 *KODE PAIRING*

code : \`${formatPairingCode(code)}\`

📱 Number:${waNumber}
⏳ Berlaku 90 detik`,
      {
        parse_mode: 'Markdown',
        reply_markup: Markup.inlineKeyboard([
          [ Markup.button.callback('「 𝙲𝚊𝚗𝚌𝚎𝚕 」', 'CANCEL_PAIRING')]
        ]).reply_markup
      }
    )

    const startTime = Date.now()

    PAIRING_TIMER[userId] = setInterval(async () => {
      const online = getSession(String(userId))?.sock?.user

      if (online) {
        ensureUserData(userId)
        const sender = getSession(String(userId))
          ?.sock?.user?.id?.split(':')[0]

        if (!CEKBIO_MODE[userId].startTime) {
          CEKBIO_MODE[userId].startTime = Date.now()
        }
        CEKBIO_MODE[userId].lastOnline = Date.now()
        CEKBIO_MODE[userId].lastSender = sender
        saveUserData(CEKBIO_MODE)

        resetUser(userId)

        await ctx.telegram.editMessageText(
          ctx.chat.id,
          PAIRING_MSG[userId],
          null,
          '✅ *Pairing berhasil*',
          { parse_mode: 'Markdown' }
        )
        setTimeout(async() => {
           await ctx.telegram.deleteMessage(
             ctx.chat.id,
             PAIRING_MSG[userId]
           ).catch(() => {})

           await ctx.reply(
             dashboardText(userId),
             {
               parse_mode: 'Markdown',
               reply_markup: dashboardKeyboard(userId).reply_markup
             }
           )
         }, 2000)

         return
       }

      if (Date.now() - startTime > 90_000) {
        clearInterval(PAIRING_TIMER[userId])
        delete PAIRING_TIMER[userId]

        resetUser(userId)
        const session = getSession(String(userId))
        try {
          await session?.sock?.logout()
        } catch {}
        await ctx.telegram.editMessageText(
          ctx.chat.id,
          PAIRING_MSG[userId],
          null,
          '⏰ Pairing timeout\nulangi /pairing jika ingin melanjut kan '
        )
      }
    }, 5000)

  } catch (e) {
    resetUser(userId)
    await ctx.reply('❌ Gagal pairing')
  }
}

/* ================= MAIN ================= */

export default function pairing(bot) {
  console.log('✅ pairing  command loaded')
  bot.command('pairing', async (ctx) => {
    const userId = ctx.from.id

    if (PAIRING_ACTIVE[userId] || CHANGE_ACTIVE[userId]) {
      return ctx.reply(
        '⏳ *Proses pairing masih berjalan*\n\n' +
        'Selesaikan pairing atau tekan *Cancel Pairing*',
        { parse_mode: 'Markdown' }
      )
    }
    resetUser(userId)
    await ctx.reply(
      dashboardText(userId),
      {
        parse_mode: 'Markdown',
        reply_markup: dashboardKeyboard(userId).reply_markup
      }
    )
  })

  bot.action('ADD_SENDER', async (ctx) => {
    const userId = ctx.from.id

  // guard: kalau masih pairing
    if (PAIRING_ACTIVE[userId]) {
      return ctx.answerCbQuery('⏳ Pairing masih berlangsung')
    }

    USER_STATE[userId] = 'INPUT_PAIRING_NUMBER'

  // EDIT dashboard → input nomor
    await ctx.telegram.editMessageText(
      ctx.chat.id,
      ctx.callbackQuery.message.message_id,
       null,
       `📩 *Masukkan nomor WhatsApp*\n\n` +
       `Gunakan format internasional tanpa tambahan di awal dan spasi\n` +
       `contoh: \`628123456789\`.`,
      {
         parse_mode: 'Markdown',
         reply_markup: Markup.inlineKeyboard([
           [Markup.button.callback('「 𝙲𝚊𝚗𝚌𝚎𝚕 」', 'CANCEL_INPUT')]
         ]).reply_markup
      }
    )

    ctx.answerCbQuery()
  })

  bot.action('CANCEL_INPUT', async (ctx) => {
    const userId = ctx.from.id

    USER_STATE[userId] = null

  // balik ke dashboard
    await ctx.telegram.editMessageText(
      ctx.chat.id,
      ctx.callbackQuery.message.message_id,
      null,
      dashboardText(userId),
      {
        parse_mode: 'Markdown',
        reply_markup: dashboardKeyboard(userId).reply_markup
      }
    )

    ctx.answerCbQuery('Dibatalkan')
  })

  bot.action('CANCEL_PAIRING', async (ctx) => {
    const userId = ctx.from.id
    updateLastOnline(userId)
    resetUser(userId)

    const session = getSession(String(userId))
    await session?.sock?.logout().catch(() => {})

    await ctx.reply('❌ Pairing dibatalkan')
    await ctx.telegram.deleteMessage(
      ctx.chat.id,
      ctx.callbackQuery.message.message_id
    ).catch(() => {})

    ctx.answerCbQuery('Proses di batalkan')
  })

  bot.action('DISCONNECT', async (ctx) => {
    const userId = ctx.from.id

  /*==== stop pairing kalau ada == */
    if (PAIRING_TIMER[userId]) {
      clearInterval(PAIRING_TIMER[userId])
      delete PAIRING_TIMER[userId]

    }
    PAIRING_ACTIVE[userId] = false
    USER_STATE[userId] = null

  /*====== LOGOUT SOCKET ========= */
    const session = getSession(String(userId))
    try {
      await session?.sock?.logout()
    } catch (e) {
      console.log('[DISCONNECT] logout error ignored')
    }
  /* ===== HAPUS DATA USER TOTAL ===== */
    if (CEKBIO_MODE[userId]) {
      delete CEKBIO_MODE[userId]
      saveUserData(CEKBIO_MODE)
    }
    await ctx.telegram.editMessageText(
      ctx.chat.id,
      ctx.callbackQuery.message.message_id,
      null,
      '❌ *Sender terputus*\n\nApa yang ingin kamu lakukan?',
      {
        parse_mode: 'Markdown',
        reply_markup: Markup.inlineKeyboard([
          [Markup.button.callback('「 𝙰𝚍𝚍 𝚂𝚎𝚗𝚍𝚎𝚛 」', 'ADD_SENDER')]
        ]).reply_markup
      }
    )

    ctx.answerCbQuery('Disconnected')
  })

  bot.action('BACK_TO_DASHBOARD', async (ctx) => {
    const userId = ctx.from.id

    USER_STATE[userId] = null
    CHANGE_ACTIVE[userId] = false

    await ctx.telegram.editMessageText(
      ctx.chat.id,
      ctx.callbackQuery.message.message_id,
      null,
      dashboardText(userId),
      {
        parse_mode: 'Markdown',
        reply_markup: dashboardKeyboard(userId).reply_markup
      }
    )

    ctx.answerCbQuery()
  })

 // ========== CANGE ============ //
  bot.action('CHANGE_SENDER', async (ctx) => {
    const userId = ctx.from.id

    if (CHANGE_ACTIVE[userId]) {
      return ctx.answerCbQuery('Proses masih berjalan')
    }
    CHANGE_ACTIVE[userId] = true
    USER_STATE[userId] = 'INPUT_CHANGE_NUMBER'

    await ctx.telegram.editMessageText(
      ctx.chat.id,
      ctx.callbackQuery.message.message_id,
      null,
      '🔄 *Ganti Sender WhatsApp*\n\n' +
      'Sender lama akan di hapus.\n' +
      'kirim nomor baru dengan format internasional\n' +
      'contoh : \`584269580420\`.',
      {
        parse_mode: 'Markdown',
        reply_markup: Markup.inlineKeyboard([
          [ Markup.button.callback('「 𝙲𝚊𝚗𝚌𝚎𝚕 」', 'BACK_TO_DASHBOARD')]
       ]).reply_markup
      }
    )

    ctx.answerCbQuery()
  })

  bot.action('RECONNECT', async (ctx) => {
    const userId = ctx.from.id
    const msgId = ctx.callbackQuery.message.message_id

  // pastikan ada riwayat
    const data = CEKBIO_MODE[userId]
    if (!data?.lastSender) {
      return ctx.answerCbQuery('❌ Tidak ada sender sebelumnya')
    }

    resetUser(userId)
    await ctx.telegram.editMessageText(
      ctx.chat.id,
      msgId,
      null,
      '🔄 _Menghubungkan ulang_...',
      { parse_mode: 'Markdown'}
    )

    ctx.answerCbQuery('🔄 Menghubungkan ulang...')
    await new Promise(r => setTimeout(r, 800))

  // langsung pairing pakai nomor terakhir
    await startPairing(ctx, userId, data.lastSender)
  })

 // ============ SET MODE ============= //
  bot.action('CEKBIO_MODE', async (ctx) => {
    const userId = ctx.from.id
    const current = CEKBIO_MODE[userId] || 'medium'
    const menu = renderModeMenu(userId)

    await ctx.telegram.editMessageText(
      ctx.chat.id,
      ctx.callbackQuery.message.message_id,
      null,
      menu.text,
      {
        parse_mode: 'Markdown',
        reply_markup: menu.keyboard.reply_markup
      }
    )

    ctx.answerCbQuery()
  })

  bot.action('MODE_SLOW', ctx => setMode(ctx, 'slow'))
  bot.action('MODE_MEDIUM', ctx => setMode(ctx, 'medium'))
  bot.action('MODE_FAST', ctx => setMode(ctx, 'fast'))

  bot.on('text', async (ctx, next) => {
    if (ctx.message.text.startsWith('/')) {
      return next()
    }
    const userId = ctx.from.id
    const number = ctx.message.text.trim()

  // validasi nomor HANYA saat memang sedang input nomor
    if (
      USER_STATE[userId] === 'INPUT_PAIRING_NUMBER' ||
      USER_STATE[userId] === 'INPUT_CHANGE_NUMBER'
    ) {
      if (!/^\d{10,15}$/.test(number)) {
        return ctx.reply('❌ Nomor tidak valid')
      }
    } else {
    // bukan dalam mode input → abaikan text
      return
    }

  /* ===== PAIRING BARU ===== */
    if (USER_STATE[userId] === 'INPUT_PAIRING_NUMBER') {
      USER_STATE[userId] = null
      return startPairing(ctx, userId, number)
    }

  /* ===== CHANGE SENDER ===== */
    if (USER_STATE[userId] === 'INPUT_CHANGE_NUMBER') {
      USER_STATE[userId] = null

      const loading = await ctx.reply('♻️ Mengganti sender WhatsApp...')

      const session = getSession(String(userId))
      try {
        await session?.sock?.logout()
      } catch {}

      startPairing(ctx, userId, number)

      await ctx.telegram.deleteMessage(
        ctx.chat.id,
        loading.message_id
      ).catch(() => {})
      return
    }
  })
}

