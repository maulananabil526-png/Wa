import fs from 'fs'
import path from 'path'
import P from 'pino'
import { Boom } from '@hapi/boom'
import makeWASocket, {
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  DisconnectReason
} from '@whiskeysockets/baileys'
import { CEKBIO_CANCEL } from './state.js'

const BASE_DIR = process.cwd()
const SESSIONS_DIR = path.join(BASE_DIR, 'sessions')

if (!fs.existsSync(SESSIONS_DIR)) {
  fs.mkdirSync(SESSIONS_DIR, { recursive: true })
}

const sessions = {}
// =================  START SOCKET ================ //
export async function startSocket(userId) {
  const sessionPath = path.join(SESSIONS_DIR, String(userId))

  if (sessions[userId]?.sock) {
    return sessions[userId].sock
  }

  if (!fs.existsSync(sessionPath)) {
    fs.mkdirSync(sessionPath, { recursive: true })
  }

  const { state, saveCreds } = await useMultiFileAuthState(sessionPath)
  const { version } = await fetchLatestBaileysVersion()

  const sock = makeWASocket({
    auth: state,
    version,
    printQRInTerminal: false,
    logger: P({ level: 'silent' }),
    browser: ['Ubuntu', 'Chrome', '20.0.04']
  })

  sessions[userId] = {
    sock,
    pairing: false
  }

  sock.ev.on('creds.update', saveCreds)

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect } = update

    if (!sessions[userId]) return
   // ======== OPEN ======== //
    if (connection === 'open') {
      console.log(`✅ [${userId}] WhatsApp CONNECTED`)

      const metaPath = path.join(sessionPath, 'meta.json')
      if (!fs.existsSync(metaPath)) {
        fs.writeFileSync(
          metaPath,
          JSON.stringify(
            {startTime: Date.now() },
            null,
            2
          )
        )
      }
      sessions[userId].pairing = false
      return
    }

   // ======= CLOSE ======= //
    if (connection === 'close') {
      const code = new Boom(lastDisconnect?.error)?.output?.statusCode

      let reason = 'Tidak diketahui'
      if (code === DisconnectReason.loggedOut) reason = 'Logout dari WhatsApp'
      else if (code === 401) reason = 'Unauthorized (401)'
      else if (code === 403) reason = 'Forbidden / Banned (403)'
      else if (code === 428) reason = 'Connection closed (428)'
      else if (code === 440) reason = 'Session conflict (440)'
      else if (code === 515) reason = 'Restart required (515)'
      else if (code === DisconnectReason.connectionClosed) reason = 'Koneksi ditutup server'
      else if (code === DisconnectReason.connectionLost) reason = 'Koneksi internet terputus'
      else if (code === DisconnectReason.timedOut) reason = 'Koneksi timeout'

      console.log(`❌ [${userId}] Disconnected: ${code}`)
      try {
        CEKBIO_CANCEL[userId] = true
        CEKBIO_CANCEL[`${userId}_REASON`] = reason
      } catch {}

      if (!sessions[userId]) return
      sessions[userId].pairing = false

    // ===== LOGOUT ====//
      if (
        code === DisconnectReason.loggedOut ||
        code === 401 ||
        code === 403
      ){
        console.log(`🧹 [${userId}] Logged out, hapus session`)
        try {
          fs.rmSync(sessionPath, { recursive: true, force: true })
        } catch {}
        delete sessions[userId]
        return
      }

     // ==== RECAL RECAL ==//
      console.log(`🔄 [${userId}] Reconnecting...`)
      delete sessions[userId]
      setTimeout(() => {
        startSocket(userId)
      }, 5000)
    }
  })

  return sock
}

//============ GET SESSION =========== //
export function getSession(userId) {
  return sessions[userId] || null
}
// ============== CEK NOMOR ================= //
export async function checkNumber(sock, number) {
  try {
    const jid = number + '@s.whatsapp.net'
    const [res] = await sock.onWhatsApp(jid)
    return !!res?.exists
  } catch (e) {
    return false
  }
}

// ========= CEKBIO HELPER ========= //
export async function getBio(sock, number) {
  try {
    const jid = number + '@s.whatsapp.net'
    const res = await sock.fetchStatus(jid)

    // 🔧 PATCH: cegah 1970-01-01
    const raw = res?.[0]?.status?.setAt
    const setAt =
      raw && raw > 1000000000
        ? new Date(raw)
        : null

    const bio = res?.[0]?.status?.status || null

    return { bio, setAt }
  } catch (e) {
    return { bio: null, setAt: null }
  }
}
// ============== META BUSINESS ================= //
export async function checkMetaBusiness(sock, number) {
  try {
    const jid = number + '@s.whatsapp.net'
    const biz = await sock.getBusinessProfile(jid)
    return !!biz
  } catch (e) {
    return false
  }
}
