// The planner's rules (กติกาตาราง) and the reminder times (W10 ⑤), on the settings page.
// กติกาตาราง lived on the schedule page until the user agreed (2026-11-06) that settings belong
// here, as in the plan's W10. Both cards change the same setting (/api/schedule/rules), so the
// settings page loads it once and both save through useScheduleRules: each save sends the latest
// values with only its own part changed, so one card never undoes what the other just saved.
import { useEffect, useState } from "react";
import { api, type ScheduleRules } from "../../api";
import { Button, Card, Spinner } from "../../components/ui";
import { duration } from "../../format";
import { field, TimeSelect } from "../schedule/EditCard";

type Body = Parameters<typeof api.saveRules>[0];

export function useScheduleRules() {
  const [rules, setRules] = useState<ScheduleRules | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.rules().then(setRules, (e) => setError((e as Error).message)); }, []);
  const save = async (patch: Partial<Body>) => {
    if (!rules) return;
    const r = rules.rules;
    const body: Body = { day_start: r.day_start, day_end: r.day_end, max_block: r.max_block, per_task_per_day: r.per_task_per_day,
                         gap: r.gap, estimates: rules.estimates, reminders: rules.reminders, ...patch };
    await api.saveRules(body);
    setRules({ ...rules, rules: { ...r, day_start: body.day_start, day_end: body.day_end, max_block: body.max_block,
                                  per_task_per_day: body.per_task_per_day, gap: body.gap },
               estimates: body.estimates, reminders: body.reminders });
  };
  return { rules, error, save };
}

type Rules = ReturnType<typeof useScheduleRules>;

/** W10 ⑤: how long before an appointment or a due date #ด่วน reminds you. A press saves it
 *  (recorded, ย้อนกลับ in สิ่งที่เลขาทำ). */
export function Reminders({ rules, error, save }: Rules) {
  const [msg, setMsg] = useState("");
  const toggle = async (lead: string) => {
    if (!rules) return;
    setMsg("");
    const reminders = rules.reminders.includes(lead) ? rules.reminders.filter((x) => x !== lead) : [...rules.reminders, lead];
    try { await save({ reminders }); } catch (e) { setMsg((e as Error).message); }
  };
  return (
    <Card title="เตือนก่อนถึงกำหนด">
      {!rules ? (error ? <p className="text-xs text-bad">{error}</p> : <Spinner />) : (
        <div className="flex flex-wrap gap-1.5">
          {([["1d", "1 วัน"], ["1h", "1 ชั่วโมง"]] as const).map(([lead, label]) => {
            const on = rules.reminders.includes(lead);
            return (
              <button key={lead} type="button" aria-pressed={on} onClick={() => toggle(lead)} title={on ? "กดเพื่อปิด" : "กดเพื่อเปิด"}
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold cursor-pointer
                  ${on ? "bg-accent-soft text-accent-strong" : "bg-panel-2 text-muted line-through"}`}>{label}</button>
            );
          })}
        </div>
      )}
      <p className="text-xs text-muted pt-2">ก่อนนัดและเดดไลน์ ใน #ด่วน · กดเพื่อเปิดหรือปิด · ย้อนกลับได้ในหน้าสิ่งที่เลขาทำ</p>
      {msg && <p className="text-xs text-bad pt-1">{msg}</p>}
    </Card>
  );
}

/** How the planner places work blocks: the hours it may use, block length, time per task per
 *  day, the gap (also the break between one task's blocks), and the time a task takes when it
 *  doesn't say. A task can set its own block length and daily limit on the schedule page. */
export function RulesCard({ rules, error, save }: Rules) {
  const [draft, setDraft] = useState<ScheduleRules | null>(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { if (rules) setDraft(rules); }, [rules]);
  if (!draft) return <Card title="กติกาตาราง">{error ? <p className="text-xs text-bad">{error}</p> : <Spinner />}</Card>;
  const set = (k: keyof ScheduleRules["rules"], v: string | number) => setDraft({ ...draft, rules: { ...draft.rules, [k]: v } });
  const num = (k: "max_block" | "per_task_per_day" | "gap", opts: number[]) => (
    <select className={field} value={draft.rules[k]} onChange={(e) => set(k, Number(e.target.value))}>
      {[...new Set([...opts, draft.rules[k] as number])].sort((a, b) => a - b).map((m) => (
        <option key={m} value={m}>{m === 0 ? "ไม่เว้น" : duration(m)}</option>
      ))}
    </select>
  );
  const submit = async () => {
    setMsg("");
    const r = draft.rules;
    try {
      await save({ day_start: r.day_start, day_end: r.day_end, max_block: r.max_block, per_task_per_day: r.per_task_per_day,
                   gap: r.gap, estimates: draft.estimates });
      setMsg("บันทึกแล้ว · ตารางจะวางตามกติกาใหม่ในรอบถัดไป · ย้อนกลับได้ในหน้าสิ่งที่เลขาทำ");
    } catch (e) { setMsg((e as Error).message); }
  };
  return (
    <Card title={<span id="rules">กติกาตาราง</span>}>
      <div className="flex flex-col gap-2.5 text-sm">
        <label className="flex flex-wrap items-center gap-2">วางบล็อกช่วง
          <TimeSelect label="เริ่มวางบล็อก" value={draft.rules.day_start} onChange={(v) => set("day_start", v)} />–
          <TimeSelect label="วางบล็อกถึง" value={draft.rules.day_end} onChange={(v) => set("day_end", v)} /></label>
        <label className="flex flex-wrap items-center gap-2">บล็อกยาวไม่เกิน {num("max_block", [60, 90, 120, 180])}</label>
        <label className="flex flex-wrap items-center gap-2">งานละไม่เกินวันละ {num("per_task_per_day", [120, 180, 240, 360])}</label>
        <label className="flex flex-wrap items-center gap-2">เว้นห่างจากนัด และพักระหว่างบล็อกงานเดียวกัน {num("gap", [0, 10, 15, 30])}</label>
        <div className="flex flex-col gap-1">เวลาที่ใช้เมื่องานไม่ได้บอก (นาที)
          <div className="flex flex-wrap gap-2">
            {Object.entries({ classroom: "Classroom", email: "อีเมล", you: "คุณเพิ่ม" }).map(([k, label]) => (
              <label key={k} className="flex items-center gap-1 text-xs">{label}
                <input type="number" min={15} max={1440} step={15} className={`${field} w-20`} value={draft.estimates[k] ?? 60}
                  onChange={(e) => setDraft({ ...draft, estimates: { ...draft.estimates, [k]: Number(e.target.value) } })} /></label>
            ))}
          </div>
        </div>
        <p className="text-xs text-muted">ขนาดบล็อกและเวลาต่อวันตั้งเป็นรายงานได้ในหน้าตาราง · งานที่ไม่ได้ตั้งใช้ค่าตามนี้</p>
        <div className="flex flex-wrap items-center gap-2"><Button kind="p" sm onClick={submit}>บันทึกกติกา</Button>
          {msg && <span className="text-xs text-muted">{msg}</span>}</div>
      </div>
    </Card>
  );
}
