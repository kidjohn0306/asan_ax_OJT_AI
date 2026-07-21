import KoreanLunarCalendar from 'korean-lunar-calendar'

const FIXED_HOLIDAYS = [
  { month: 1, day: 1, name: '신정', substitutable: false },
  { month: 3, day: 1, name: '삼일절', substitutable: true },
  { month: 5, day: 5, name: '어린이날', substitutable: true },
  { month: 6, day: 6, name: '현충일', substitutable: false },
  { month: 8, day: 15, name: '광복절', substitutable: true },
  { month: 10, day: 3, name: '개천절', substitutable: true },
  { month: 10, day: 9, name: '한글날', substitutable: true },
  { month: 12, day: 25, name: '성탄절', substitutable: true },
]

// 국무회의 의결 등으로 그때그때 지정되는 임시공휴일처럼, 규칙이나 천문 계산으로는
// 알 수 없는 날짜를 발표되는 대로 여기에 추가한다. substitutable은 기본 false —
// 임시공휴일은 이미 확정된 하루라 별도 대체공휴일을 다시 계산할 필요가 없다.
const MANUAL_HOLIDAYS = [
  // { date: '2026-08-17', name: '임시공휴일', substitutable: false },
]

function lunarToSolar(year, month, day) {
  const cal = new KoreanLunarCalendar()
  if (!cal.setLunarDate(year, month, day, false)) return null
  const solar = cal.getSolarCalendar()
  return new Date(solar.year, solar.month - 1, solar.day)
}

function addDays(date, n) {
  const d = new Date(date)
  d.setDate(d.getDate() + n)
  return d
}

function toDateStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const holidayCache = new Map()

// 대체공휴일: 설날/추석/어린이날/삼일절/광복절/개천절/한글날/부처님오신날/성탄절 대상.
// 신정·현충일은 제외 (관공서의 공휴일에 관한 규정, 2023.11.17. 시행 개정 기준).
export function getKoreanHolidays(year) {
  if (holidayCache.has(year)) return holidayCache.get(year)

  const entries = FIXED_HOLIDAYS.map(h => ({
    date: new Date(year, h.month - 1, h.day),
    name: h.name,
    substitutable: h.substitutable,
  }))

  const seollal = lunarToSolar(year, 1, 1)
  if (seollal) {
    entries.push(
      { date: addDays(seollal, -1), name: '설날', substitutable: true },
      { date: seollal, name: '설날', substitutable: true },
      { date: addDays(seollal, 1), name: '설날', substitutable: true },
    )
  }

  const chuseok = lunarToSolar(year, 8, 15)
  if (chuseok) {
    entries.push(
      { date: addDays(chuseok, -1), name: '추석', substitutable: true },
      { date: chuseok, name: '추석', substitutable: true },
      { date: addDays(chuseok, 1), name: '추석', substitutable: true },
    )
  }

  const buddha = lunarToSolar(year, 4, 8)
  if (buddha) {
    entries.push({ date: buddha, name: '부처님오신날', substitutable: true })
  }

  MANUAL_HOLIDAYS
    .filter(h => h.date.startsWith(`${year}-`))
    .forEach(h => {
      const [, m, d] = h.date.split('-').map(Number)
      entries.push({ date: new Date(year, m - 1, d), name: h.name, substitutable: !!h.substitutable })
    })

  const byDate = new Map()
  entries.forEach(({ date, name, substitutable }) => {
    const key = toDateStr(date)
    if (!byDate.has(key)) byDate.set(key, { names: [], substitutable: false })
    const info = byDate.get(key)
    info.names.push(name)
    if (substitutable) info.substitutable = true
  })

  // 대체공휴일은 겹치는 날짜 하나하나가 아니라, 연속된 공휴일 구간(설날/추석 연휴 등)
  // 전체를 하나의 단위로 보고 그 구간 뒤에 하루만 지정한다 (예: 2023년 추석처럼 연휴 중
  // 이틀이 주말과 겹쳐도 대체공휴일은 하루만 생긴다).
  const sortedKeys = [...byDate.keys()].sort()
  const blocks = []
  sortedKeys.forEach(key => {
    const last = blocks[blocks.length - 1]
    if (last && toDateStr(addDays(new Date(last.lastDate), 1)) === key) {
      last.keys.push(key)
      last.lastDate = key
    } else {
      blocks.push({ keys: [key], lastDate: key })
    }
  })

  const substitutes = []
  blocks.forEach(block => {
    const triggerName = block.keys.reduce((found, key) => {
      if (found) return found
      const info = byDate.get(key)
      if (!info.substitutable) return found
      const [y, m, d] = key.split('-').map(Number)
      const dow = new Date(y, m - 1, d).getDay()
      const isWeekend = dow === 0 || dow === 6
      const overlapsMultiple = info.names.length > 1
      return (isWeekend || overlapsMultiple) ? info.names[0] : found
    }, null)
    if (!triggerName) return

    const [ly, lm, ld] = block.lastDate.split('-').map(Number)
    let next = addDays(new Date(ly, lm - 1, ld), 1)
    for (;;) {
      const nextKey = toDateStr(next)
      const nextDow = next.getDay()
      const alreadyHoliday = byDate.has(nextKey) || substitutes.some(s => s.key === nextKey)
      if (nextDow !== 0 && nextDow !== 6 && !alreadyHoliday) {
        substitutes.push({ key: nextKey, name: `${triggerName} 대체공휴일` })
        break
      }
      next = addDays(next, 1)
    }
  })

  substitutes.forEach(({ key, name }) => {
    if (!byDate.has(key)) byDate.set(key, { names: [], substitutable: false })
    byDate.get(key).names.push(name)
  })

  holidayCache.set(year, byDate)
  return byDate
}

export function getHolidayInfo(dateStr) {
  const year = Number(dateStr.slice(0, 4))
  return getKoreanHolidays(year).get(dateStr) || null
}
