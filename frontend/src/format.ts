// How dates, times and token counts read on the page (the same style as the mockups).

const DAYS = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"]; // Date.getDay(): 0 = Sunday
const MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];

/** "พุธ 5 พ.ย. 2569" (Buddhist-era year, as in the mockups). */
export function thaiDate(d: Date = new Date()): string {
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear() + 543}`;
}

/** "14:05", or "5 พ.ย. 14:05" when it isn't today. */
export function when(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const hm = d.toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit", hour12: false });
  return d.toDateString() === new Date().toDateString() ? hm : `${d.getDate()} ${MONTHS[d.getMonth()]} ${hm}`;
}

/** 90 -> "1 ชม. 30 นาที", 45 -> "45 นาที". */
export function duration(min: number): string {
  if (min < 60) return `${min} นาที`;
  const h = Math.floor(min / 60), m = min % 60;
  return m ? `${h} ชม. ${m} นาที` : `${h} ชม.`;
}

const DAYS_SHORT = ["อา.", "จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส."];

/** "พฤ. 12 พ.ย." */
export function shortDay(d: Date): string {
  return `${DAYS_SHORT[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

const pad = (n: number) => String(n).padStart(2, "0");

/** "2026-11-12": the local date, as a date input wants it. */
export function ymd(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** "09:30": the local time, 24-hour, as a time input wants it. */
export function hm(d: Date): string {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** 2350 -> "2.4k" */
export function tokens(n: number | null | undefined): string {
  if (!n) return "0";
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}
