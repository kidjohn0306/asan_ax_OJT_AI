// 시험 관리 화면에서 월간 일정 탐색과 날짜 선택을 제공하는 공통 달력
import { useEffect, useMemo, useState } from 'react'

import './ExamSchedule.css'

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

function pad(value) {
  return String(value).padStart(2, '0')
}

export function toExamDateKey(value) {
  if (!value) return ''
  const text = String(value)
  const datePrefix = text.match(/^(\d{4})-(\d{2})-(\d{2})/)
  const hasExplicitTimeZone = /(?:z|[+-]\d{2}:\d{2})$/i.test(text)
  // datetime-local 값은 적힌 날짜를 보존하고, UTC·오프셋 값은 관리자 현지 날짜로 환산한다.
  if (datePrefix && !hasExplicitTimeZone) return `${datePrefix[1]}-${datePrefix[2]}-${datePrefix[3]}`
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function parseDateKey(dateKey) {
  const match = String(dateKey || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!match) return null
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12)
}

function startOfMonth(dateKey) {
  const selected = parseDateKey(dateKey)
  const base = selected || new Date()
  return new Date(base.getFullYear(), base.getMonth(), 1, 12)
}

function monthKey(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}`
}

function buildCalendarDays(monthDate) {
  const first = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1, 12)
  const gridStart = new Date(first)
  gridStart.setDate(1 - first.getDay())
  return Array.from({ length:42 }, (_, index) => {
    const date = new Date(gridStart)
    date.setDate(gridStart.getDate() + index)
    return {
      date,
      dateKey:`${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
      inMonth:date.getMonth() === monthDate.getMonth(),
    }
  })
}

export default function ExamScheduleCalendar({
  exams = [],
  selectedDate = '',
  onSelectDate,
  statusResolver = () => 'scheduled',
  compact = false,
  ariaLabel = '시험 일정 달력',
}) {
  const [visibleMonth, setVisibleMonth] = useState(() => startOfMonth(selectedDate))
  const todayKey = toExamDateKey(new Date())

  useEffect(() => {
    const selected = parseDateKey(selectedDate)
    if (selected && monthKey(selected) !== monthKey(visibleMonth)) {
      setVisibleMonth(new Date(selected.getFullYear(), selected.getMonth(), 1, 12))
    }
  }, [selectedDate])

  const eventsByDate = useMemo(() => {
    const grouped = new Map()
    exams.forEach(exam => {
      const dateKey = toExamDateKey(exam.exam_datetime)
      if (!dateKey) return
      const entries = grouped.get(dateKey) || []
      entries.push({ ...exam, scheduleStatus:statusResolver(exam) })
      grouped.set(dateKey, entries)
    })
    return grouped
  }, [exams, statusResolver])

  const days = useMemo(() => buildCalendarDays(visibleMonth), [visibleMonth])

  function moveMonth(offset) {
    setVisibleMonth(current => new Date(current.getFullYear(), current.getMonth() + offset, 1, 12))
  }

  return (
    <section className={`exam-schedule-calendar${compact ? ' is-compact' : ''}`} aria-label={ariaLabel}>
      <div className="exam-schedule-calendar__header">
        <button type="button" className="exam-schedule-icon-button" onClick={() => moveMonth(-1)} aria-label="이전 달">‹</button>
        <strong>{visibleMonth.getFullYear()}년 {visibleMonth.getMonth() + 1}월</strong>
        <button type="button" className="exam-schedule-icon-button" onClick={() => moveMonth(1)} aria-label="다음 달">›</button>
      </div>
      <div className="exam-schedule-calendar__weekdays" aria-hidden="true">
        {WEEKDAYS.map(day => <span key={day}>{day}</span>)}
      </div>
      <div className="exam-schedule-calendar__grid">
        {days.map(({ date, dateKey, inMonth }) => {
          const events = eventsByDate.get(dateKey) || []
          const isSelected = selectedDate === dateKey
          const label = `${date.getMonth() + 1}월 ${date.getDate()}일${events.length ? `, 시험 ${events.length}건` : ', 시험 없음'}`
          return (
            <button
              type="button"
              key={dateKey}
              className={`exam-schedule-day${inMonth ? '' : ' is-outside'}${isSelected ? ' is-selected' : ''}${todayKey === dateKey ? ' is-today' : ''}`}
              onClick={() => onSelectDate?.(dateKey)}
              aria-label={label}
              aria-pressed={isSelected}
            >
              <span className="exam-schedule-day__number">{date.getDate()}</span>
              <span className="exam-schedule-day__events" aria-hidden="true">
                {events.slice(0, compact ? 3 : 2).map(exam => (
                  <span key={exam.exam_id} className={`exam-schedule-event is-${exam.scheduleStatus}`}>
                    <i />
                    {!compact && <em>{exam.name}</em>}
                  </span>
                ))}
                {!compact && events.length > 2 && <span className="exam-schedule-more">+{events.length - 2}건</span>}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
