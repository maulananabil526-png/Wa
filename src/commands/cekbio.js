import fs from 'fs'
import path from 'path'
import axios from 'axios'

import {
  getSession,
  checkNumber,
  getBio,
  checkMetaBusiness
} from '../whatsapp.js'

import {
  CEKBIO_MODE,
  CEKBIO_RUNNING,
  CEKBIO_QUEUE,
  CEKBIO_CANCEL,
  PANEL_STATE
} from '../state.js'

/* ================== MEMORY FILE CONTEXT ================== */
const LAST_FILE = {}        // file terakhir user
const STATUS_MSG = {}      // message id status utama

/* ================== UTIL ================== */

const wait = (ms) => new Promise(r => setTimeout(r, ms))
const USER_DATA_FILE = path.join(
  process.cwd(),
  'src/storage/user_data.json'
)

function loadUserData() {
  try {
    if (fs.existsSync(USER_DATA_FILE)) {
      return JSON.parse(fs.readFileSync(USER_DATA_FILE, 'utf8'))
    }
  } catch {}
  return {}
}

export function saveUserData(data) {
  try {
    fs.writeFileSync(USER_DATA_FILE, JSON.stringify(data, null, 2))
  } catch (e) {
    console.error('[USER DATA SAVE ERROR]', e)
  }
}

Object.assign(CEKBIO_MODE, loadUserData())

export function ensureUserData(userId) {
  if (!CEKBIO_MODE[userId]) {
    CEKBIO_MODE[userId] = {
      mode: 'medium',
      startTime: null,
      lastOnline: null,
      lastSender: null
    }
  }
}

export function removeUserData(userId) {
  if (CEKBIO_MODE[userId]) {
    delete CEKBIO_MODE[userId]
    saveUserData(CEKBIO_MODE)
  }
}


function normalize(num) {
  let n = num.replace(/\D/g, '')
  if (n.startsWith('0')) n = '62' + n.slice(1)
  if (n.startsWith('8')) n = '62' + n
  return n
}

function getConfig(mode, activeUsers) {
  if (mode === 'slow') return { batch: 10, delay: 2500 }
  if (mode === 'fast') {
    if (activeUsers > 50) return { batch: 20, delay: 800 }
    if (activeUsers > 20) return { batch: 26, delay: 600 }
    return { batch: 36, delay: 400 }
  }
  return { batch: 22, delay: 700 }
}

function fmtTime(date) {
  if (!date) return 'Tidak diketahui'
  try { return new Date(date).toLocaleString('id-ID') }
  catch { return 'Gagal memproses waktu' }
}

function formatDuration(ms) {
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}

function progressBar(done, total, length = 14) {
  if (total === 0) return '[░░░░░░░░░░░░░░] 0%'
  const filled = Math.round(length * done / total)
  const percent = Math.round((done / total) * 100)
  return `[${'█'.repeat(filled)}${'░'.repeat(length - filled)}] ${percent}%`
}

async function withTimeoutSafe(promise, ms = 10000) {
  let timeoutId
  const timeoutPromise = new Promise(resolve => {
    timeoutId = setTimeout(() => resolve(null), ms)
  })
  const result = await Promise.race([promise, timeoutPromise])
  clearTimeout(timeoutId)
  return result
}

/* ================== PANEL SCALE LIMITER ================== */

async function acquireSlot() {
  while (PANEL_STATE.ACTIVE_TASKS >= PANEL_STATE.MAX_TASKS) {
    await wait(50)
  }
  PANEL_STATE.ACTIVE_TASKS++
}

function releaseSlot() {
  PANEL_STATE.ACTIVE_TASKS--
}

/* ================== OUTPUT BUILDER ================== */

function buildOutput(results, meta) {
  const withBio = []
  const registeredOnly = []
  const notRegistered = []

  for (const r of results) {
    if (!r.registered) notRegistered.push(r.number)
    else {
      const hasBio = r.bio && r.bio.trim()
      const hasSet = !!r.setAt
      if (hasBio || hasSet) withBio.push(r)
      else registeredOnly.push(r)
    }
  }

  withBio.sort((a, b) => {
    const ta = a.setAt ? new Date(a.setAt).getTime() : Infinity
    const tb = b.setAt ? new Date(b.setAt).getTime() : Infinity
    return ta - tb
  })

  const businessCount = results.filter(r => r.metaBusiness).length

  let text =
`📋 HASIL CEKBIO
Tanggal  : ${new Date().toLocaleString('id-ID')}
=================================
📊 Total Dicek : ${meta.total}
▪• Ada Bio     : ${withBio.length}
 • Terdaftar   : ${withBio.length + registeredOnly.length}
 • Tidak Ada   : ${notRegistered.length}
 • Business    : ${businessCount}
 • Durasi      : ${meta.duration}
 • Mode        : ${meta.mode.toUpperCase()}

`

  if (withBio.length) {
    text += '🟢 ADA BIO\n'
    withBio.forEach((r, i) => {
      const label = r.metaBusiness ? ' [•BUSINESS•]' : ''
      text +=
`${i + 1}) ${r.number}${label}
   • Bio : ${r.bio && r.bio.trim() ? r.bio : '-'}
   • Set : ${fmtTime(r.setAt)}

`
    })
  }

  if (registeredOnly.length) {
    text += '🟡 TERDAFTAR (Tanpa Bio)\n'
    registeredOnly.forEach((r, i) => {
      const label = r.metaBusiness ? ' [•BUSINESS•]' : ''
      text += `${i + 1}) ${r.number}${label}\n`
    })
    text += '\n'
  }

  if (notRegistered.length) {
    text += '🔴 TIDAK TERDAFTAR\n'
    notRegistered.forEach((n, i) => {
      text += `${i + 1}) ${n}\n`
    })
  }

  return text
}

// ================== CAPTION BUILDER ==================
function buildPremiumCaption({ results, mode, durationText, sourceLabel }) {
  const total = results.length
  const registered = results.filter(r => r.registered).length
  const withBio = results.filter(r => (r.bio && r.bio.trim()) || r.setAt).length
  const business = results.filter(r => r.metaBusiness).length
  const notRegistered = total - registered

  return (
`✨ *_hasil cekbio_* ✨

❒ *_Ringkasan Data_*
  • Total Nomor       : *${total}*
  • Terdaftar         : *${registered}*
  • Dengan Bio        : *${withBio}*
  • Akun Business     : *${business}*
  • Tidak Terdaftar   : *${notRegistered}*

❒ *_ Mode_*  : *${mode.toUpperCase()}*
❒*_ Durasi_* : *${durationText}*
  ${new Date().toLocaleString('id-ID')}`

  )
}

/* ================== STATUS UI ================== */

async function editStatus(ctx, text, buttons = null) {
  const userId = String(ctx.from.id)
  const msgId = STATUS_MSG[userId]
  if (!msgId) return

  await ctx.telegram.editMessageText(
    ctx.chat.id,
    msgId,
    null,
    text,
    buttons ? { reply_markup: { inline_keyboard: buttons } } : undefined
  ).catch(() => {})
}

/* ================== JOB RUNNER ================== */

async function runCekbioJob(ctx, numbers, mode, sourceLabel) {
  const userId = String(ctx.from.id)
  const startTime = Date.now()

  CEKBIO_RUNNING[userId] = true
  CEKBIO_CANCEL[userId] = false

  let userCounted = false
  PANEL_STATE.ACTIVE_USERS++
  userCounted = true

  try {
    const session = getSession(userId)
    if (!session?.sock?.user) {
      return editStatus(ctx, '❌ Sender WhatsApp belum aktif\nGunakan /pairing')
    }

    const sock = session.sock
    const { batch, delay } = getConfig(mode, PANEL_STATE.ACTIVE_USERS)

    await editStatus(
      ctx,
      `⏳ Menyiapkan proses pengecekan...`,
      [[{ text: '❌ Cancel', callback_data: 'cekbio_cancel' }]]
    )

    if (numbers.length > 5000) {
      await ctx.reply(
        `⚠️ *PERINGATAN*\n` +
        `Terdapat ${numbers.length} nomor dalam input\n` +
        `Proses akan memakan waktu lama\n\n` +
        `gunakan cekbio sewajar nya...`,
        {parse_mode: 'Markdown' }
      )
    }

    const results = []
    let done = 0

    for (let i = 0; i < numbers.length; i += batch) {

      const liveSession = getSession(userId)
      if (!liveSession?.sock?.user) {
        CEKBIO_CANCEL[userId] = true
        const reason = CEKBIO_CANCEL[`${userId}_REASON`] || 'Tidak diketahui'

        await editStatus(
          ctx,
          `🔴 Sender WhatsApp terputus\n` +
          `📛 Alasan: ${reason}\n` +
          `Proses dihentikan otomatis`
        )
        break
      }
      if (CEKBIO_CANCEL[userId]) {
        await editStatus(ctx, '🛑 Proses dibatalkan oleh user')
        break
      }

      const chunk = numbers.slice(i, i + batch)

      const tasks = chunk.map(async (num) => {
        await acquireSlot()
        try {
          const liveSession = getSession(userId)
          if (!liveSession?.sock?.user) throw new Error('SOCKET_DEAD')

          const registered = await withTimeoutSafe(checkNumber(sock, num), 8000)
          if (!registered) {
            return { number: num, registered: false, bio: null, setAt: null, metaBusiness: false }
          }

          const bioRes = await withTimeoutSafe(getBio(sock, num), 12000)
          const meta = await withTimeoutSafe(checkMetaBusiness(sock, num), 12000)

          return {
            number: num,
            registered: true,
            bio: bioRes?.bio || null,
            setAt: bioRes?.setAt || null,
            metaBusiness: !!meta
          }
        } catch (e) {
          if (e.message === 'SOCKET_DEAD') {
            CEKBIO_CANCEL[userId] = true
          }

          return {
           number: num,
           registered: false,
           bio: null,
           setAt: null,
           metaBusiness: false
         }
        } finally {
          releaseSlot()
        }
      })

      const chunkResults = await Promise.all(tasks)

      for (const r of chunkResults) {
        results.push(r)
        done++
        if (CEKBIO_CANCEL[userId]) break
        await wait(0)
      }

      const bar = progressBar(done, numbers.length)
      const elapsed = formatDuration(Date.now() - startTime)

      await editStatus(
        ctx,
        `📂 File: ${sourceLabel}\n` +
        `⏳ Cekbio sedang diproses\n\n` +
        `${bar}\n` +
        `📊 ${done}/${numbers.length} nomor\n` +
        `⚡ Mode: ${mode.toUpperCase()}\n` +
        `⏱️ Elapsed: ${elapsed}`,
        [[{ text: '❌ Cancel', callback_data: 'cekbio_cancel' }]]
      )

      await wait(delay)
    }

    if (CEKBIO_CANCEL[userId]) return

    const durationText = formatDuration(Date.now() - startTime)

    // 🔄 OUTPUT ANIMATION
    await editStatus(
      ctx,
      `🧹 Merapikan data...\n` +
      `📄 Menyiapkan file output...`
    )
    await wait(900)

    await editStatus(
      ctx,
      `📄 File output siap\n` +
      `⏳ Mengunggah hasil ke Telegram...`
    )
    await wait(800)

    const output = buildOutput(results, {
      total: results.length,
      mode,
      duration: durationText,
      source: sourceLabel
    })

    const fileName = `cekbio_${userId}_${Date.now()}.txt`
    const filePath = path.join(process.cwd(), fileName)

    fs.writeFileSync(filePath, output)

    await editStatus(
      ctx,
      `✅ Proses selesai dalam ${durationText}\n` +
      `📤 Mengirim file hasil...`
    )
    const caption = buildPremiumCaption({
      results,
      mode,
      durationText,
      sourceLabel
    })


    await ctx.replyWithDocument(
      { source: filePath },
      {
       caption,
       parse_mode: 'Markdown'
      }
    )

    fs.unlinkSync(filePath)

    // 🧹 AUTO DELETE FINAL STATUS
    const msgId = STATUS_MSG[userId]
    if (msgId) {
      await wait(1500)
      await ctx.telegram.deleteMessage(ctx.chat.id, msgId).catch(() => {})
      delete STATUS_MSG[userId]
    }

  } catch (err) {
    console.error('[CEKBIO ERROR]', err)
    await editStatus(ctx,'❌ Terjadi kesalahan saat cek bio')
  } finally {
    CEKBIO_RUNNING[userId] = false
    delete CEKBIO_CANCEL[userId]
    if (userCounted) PANEL_STATE.ACTIVE_USERS--
  }
}

/* ================== COMMAND ================== */

export default function cekbio(bot) {
  console.log('✅ cekbio command loaded')

  bot.action('cekbio_cancel', async (ctx) => {
    const userId = String(ctx.from.id)
    if (!CEKBIO_RUNNING[userId]) return ctx.answerCbQuery('⚠ Tidak ada proses aktif')
    CEKBIO_CANCEL[userId] = true
    await ctx.answerCbQuery('🛑 Proses dihentikan...')
  })

  // 🗑️ CANCEL FILE (PRE-PROCESS)
  bot.action('cekbio_cancel_file', async (ctx) => {
    const userId = String(ctx.from.id)
    delete LAST_FILE[userId]
    await editStatus(ctx, '🗑️ File dibatalkan\nKirim file baru atau ketik /cekbio')
    await ctx.answerCbQuery('File dibatalkan')
  })

  // 📂 FILE ACK
  bot.on('document', async (ctx) => {
    const userId = String(ctx.from.id)
    LAST_FILE[userId] = ctx.message.document

    const msg = await ctx.reply(
      `📂 File diterima: ${ctx.message.document.file_name}\n` +
      `⏳ Siap untuk diproses\n\n` +
      `Ketik /cekbio untuk mulai\n` +
      `Atau batalkan file di bawah`,
      {
        reply_markup: {
          inline_keyboard: [[{ text: '🗑️ Batalkan File', callback_data: 'cekbio_cancel_file' }]]
        }
      }
    )

    STATUS_MSG[userId] = msg.message_id
  })

  // 🔥 HANDLER UTAMA
  bot.command('cekbio', async (ctx) => {
    const userId = String(ctx.from.id)

    if (!CEKBIO_QUEUE[userId]) CEKBIO_QUEUE[userId] = Promise.resolve()

    CEKBIO_QUEUE[userId] = CEKBIO_QUEUE[userId].then(async () => {

      let numbers = []
      ensureUserData(userId)
      let mode = CEKBIO_MODE[userId].mode
      let sourceLabel = 'Input manual'

      let fileDoc = ctx.message.document || LAST_FILE[userId]

      if (fileDoc) {
        const fileName = fileDoc.file_name
        sourceLabel = fileName

        await editStatus(ctx, `📂 File: ${fileName}\n📥 Membaca isi file...`)
        await wait(600)

        const fileLink = await ctx.telegram.getFileLink(fileDoc.file_id)
        const tempPath = path.join(process.cwd(), `upload_${Date.now()}.txt`)

        const res = await axios.get(fileLink.href, { timeout: 15000 })
        fs.writeFileSync(tempPath, res.data)

        await editStatus(ctx, `📂 File: ${fileName}\n🔎 Mengekstrak nomor...`)
        await wait(600)

        const content = fs.readFileSync(tempPath, 'utf8')
        fs.unlinkSync(tempPath)

        numbers = content
          .split(/[\s,\n]+/)
          .map(normalize)
          .filter(n => n.length >= 10 && n.length <= 15)

        delete LAST_FILE[userId]
        if (!numbers.length) {
          return editStatus(ctx, '❌ Tidak ada nomor valid di dalam file')
        }

      } else {
        const raw = ctx.message.text.replace('/cekbio', '').trim()
        const parts = raw.split(/[\s,\n]+/)

        if (['slow', 'medium', 'fast'].includes(parts[0])) {
          mode = parts.shift()
          ensureUserData(userId)
          CEKBIO_MODE[userId] = mode
          saveUserData(CEKBIO_MODE)
        }

        numbers = parts
          .map(normalize)
          .filter(n => n.length >= 10 && n.length <= 15)

        if (!numbers.length) {
           return ctx.reply(
              '❌ Tidak ada nomor valid\n\n'+
              '_contoh : /cekbio 584163007274_\n\n'+
              'atau reply file yang berisi nomor\n'+
              'upload file ke bot berupa .txt atau .csv',
              { parse_mode: 'Markdown' }
           )
        }
        const msg = await ctx.reply(
          `⏳ Menyiapkan proses pengecekan...\n\n` +
          `[░░░░░░░░░░░░░░] 0%\n` +
          `⚡ Mode: ${mode.toUpperCase()}`,
          {
            reply_markup: {
              inline_keyboard: [[{ text: '❌ Cancel', callback_data: 'cekbio_cancel' }]]
            }
          }
        )

        STATUS_MSG[userId] = msg.message_id
      }

      await runCekbioJob(ctx, numbers, mode, sourceLabel)

    }).catch(console.error)
  })
}


