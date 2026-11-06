// The mail settings (B2): keywords that reach you at once whoever sends them, what you're
// interested in lately (used when reading the subjects of people you ignore), and after how many
// days a follow-up reminds you. It lived on the people page until the user agreed (2026-11-06)
// that settings belong on the settings page, as in the plan's W10. The accounts it listed are in
// ช่องทางและบริการ on the same page now.
import { useEffect, useState } from "react";
import { api, type MailSettings } from "../../api";
import { Button, Card, Spinner } from "../../components/ui";
import { when } from "../../format";
import { field } from "../schedule/EditCard";

export function MailSettingsCard() {
  const [s, setS] = useState<MailSettings | null>(null);
  const [kw, setKw] = useState("");
  const [interests, setInterests] = useState("");
  const [days, setDays] = useState(3);
  const [msg, setMsg] = useState("");
  const fill = (x: MailSettings) => { setS(x); setKw(x.keywords.join(", ")); setInterests(x.interests.join(", ")); setDays(x.followup_days); };
  useEffect(() => { api.mailSettings().then(fill, (e) => setMsg((e as Error).message)); }, []);
  const split = (t: string) => t.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);
  const save = () => api.saveMailSettings({ keywords: split(kw), interests: split(interests), followup_days: days })
    .then((x) => { fill(x); setMsg("บันทึกแล้ว"); }, (e) => setMsg((e as Error).message));
  const title = <span id="mail">ตั้งค่าอีเมล</span>;
  if (!s) return <Card title={title}>{msg ? <p className="text-xs text-bad">{msg}</p> : <Spinner />}</Card>;
  return (
    <Card title={title} right={<span className="text-xs text-muted">{s.emails_week} ฉบับใน 7 วัน{s.last_watch ? ` · เฝ้าล่าสุด ${when(s.last_watch)}` : ""}</span>}>
      <div className="flex flex-col gap-2.5 text-sm">
        <label className="flex flex-col gap-1"><span>คีย์เวิร์ดที่แจ้งทันที (ไม่ว่าใครส่ง) · คั่นด้วย ,</span>
          <input className={field} value={kw} onChange={(e) => setKw(e.target.value)} /></label>
        <label className="flex flex-col gap-1"><span>เรื่องที่สนใจช่วงนี้ (ใช้ตอนอ่านหัวข้อจากผู้ส่งที่ไม่สนใจ)</span>
          <input className={field} value={interests} onChange={(e) => setInterests(e.target.value)} placeholder="เช่น ฝึกงาน, time-series, ทุน" /></label>
        <label className="flex items-center gap-2"><span className="grow">เตือนเรื่องค้างเมื่อเกิน</span>
          <input type="number" min={1} max={30} value={days} onChange={(e) => setDays(Number(e.target.value))} className={`${field} w-16`} /> วัน</label>
        <div className="flex items-center gap-2"><Button kind="p" sm onClick={save}>บันทึก</Button>{msg && <span className="text-xs text-muted">{msg}</span>}</div>
      </div>
    </Card>
  );
}
