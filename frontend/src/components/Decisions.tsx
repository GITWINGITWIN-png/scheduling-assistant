// One request that waits for you, as the plan's W1 "รอคุณตัดสิน" draws it: an avatar, what it is,
// one line under it, and its buttons. The bell and the today page show the same rows; answering in
// either place (or in #อนุมัติ) has the same result (B4: เรื่องที่รอคุณตัดสินรวมที่เดียว).
import { useState } from "react";
import { Link } from "react-router";
import { api, type Decision } from "../api";
import { kTokens, when } from "../format";
import { AppointmentActions, CourseActions } from "./Bell";
import { ConfirmButtons } from "./OrderParts";
import { PlanActions } from "./PlanActions";
import { Avatar, Markdown } from "./ui";

export function DecisionRow({ d, onChange }: { d: Decision; onChange?: () => void }) {
  const [open, setOpen] = useState(false);
  if (d.kind === "appointment") {
    const clash = d.clash == null ? "" : d.clash ? `ชนกับ ${d.clash}` : "ไม่ชนนัดอื่น";
    return (
      <li className="py-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <Avatar name={d.from || d.title} size="sm" />
        <span className="grow min-w-0 basis-48">
          <span className="block font-semibold text-[13.5px]">{d.from ? `นัดจาก ${d.from}: ` : "นัด: "}{d.title}</span>
          <span className={`block text-xs ${d.clash ? "text-warn" : "text-ink-2"}`}>{[d.when, clash].filter(Boolean).join(" · ")}</span>
          {d.rule && <span className="block text-xs text-warn">ขัดกติกาของคุณ: {d.rule}</span>}
        </span>
        <AppointmentActions decisionId={d.id} onChange={onChange} />
      </li>
    );
  }
  if (d.kind === "job") { // a background plan (B5): decided on the jobs page, where its model and effort can change
    const risky = (d.risks ?? []).length > 0;
    const cap = (m: string) => (m ? m[0].toUpperCase() + m.slice(1) : "");
    return (
      <li className="py-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <Avatar name={d.title} size="sm" />
        <span className="grow min-w-0 basis-48">
          <span className="block font-semibold text-[13.5px]">แผนทำต่อ {d.title}{risky ? " · งานเสี่ยงสูง" : ""}</span>
          <span className="block text-xs text-ink-2">{[risky ? d.risks!.join(" · ") : d.why, d.model && `${cap(d.model)} · ${d.effort}`,
            d.budget ? `งบ ${kTokens(d.budget)} โทเคน` : ""].filter(Boolean).join(" · ")}</span>
        </span>
        <Link to={`/jobs?plan=${d.job_id}`} className="inline-flex items-center rounded-full bg-accent text-accent-ink hover:bg-accent-strong px-3 py-1 text-xs font-medium">ดูแผน</Link>
      </li>
    );
  }
  if (d.kind === "weekly") return <WeeklyRow d={d} onChange={onChange} />; // a weekly review topic (B7)
  if (d.kind === "idea") { // a grown idea group (B6): answered on the ideas page, where the folder's name is set
    return (
      <li className="py-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <Avatar name={d.title} size="sm" />
        <span className="grow min-w-0 basis-48">
          <span className="block font-semibold text-[13.5px]">กลุ่มไอเดียโตพอ: {d.title}</span>
          <span className="block text-xs text-ink-2">{[`${d.size ?? ""} ไอเดีย`, d.about && `เกี่ยวกับ ${d.about}`, "เปิดเป็นโปรเจค หรือทำเป็นงาน"].filter(Boolean).join(" · ")}</span>
        </span>
        <Link to={`/ideas?group=${d.group_id}`} className="inline-flex items-center rounded-full bg-accent text-accent-ink hover:bg-accent-strong px-3 py-1 text-xs font-medium">ดูกลุ่ม</Link>
      </li>
    );
  }
  if (d.kind === "project_level") { // a new folder under ~/Projects (B5)
    return (
      <li className="py-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <Avatar name={d.title} size="sm" />
        <span className="grow min-w-0 basis-48">
          <span className="block font-semibold text-[13.5px]">โปรเจคใหม่ {d.title}</span>
          <span className="block text-xs text-ink-2">ตั้ง potential และความเร่งด่วน · ระหว่างรอใช้ C · 2</span>
        </span>
        <Link to="/projects" className="inline-flex items-center rounded-full border border-line-2 bg-panel hover:bg-panel-2 px-3 py-1 text-xs font-medium">ตั้งระดับ</Link>
      </li>
    );
  }
  if (d.kind === "order") { // an order from the chat that can't be undone (B9): it waits for ทำเลย
    return (
      <li className="py-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <Avatar name="สั่ง" size="sm" />
        <span className="grow min-w-0 basis-48">
          <span className="block font-semibold text-[13.5px]">คำสั่งจากแชท: {d.title}</span>
          <span className="block text-xs text-ink-2">{when(d.created_at)} · ย้อนกลับไม่ได้ จึงรอคุณกดยืนยัน · หมดเวลาใน 1 วัน</span>
        </span>
        <ConfirmButtons id={d.id} onDone={onChange} />
      </li>
    );
  }
  if (d.kind === "course") {
    return (
      <li className="py-2.5 flex flex-col gap-1.5">
        <span className="flex items-center gap-2.5">
          <Avatar name={d.title} size="sm" />
          <span className="grow min-w-0">
            <span className="block font-semibold text-[13.5px]">วิชาใน Classroom: {d.title}</span>
            <span className="block text-xs text-ink-2">ติดตามไหม: งานที่มีกำหนดส่งเข้าตาราง สื่อใหม่ลงโฟลเดอร์วิชา</span>
          </span>
        </span>
        <CourseActions decisionId={d.id} folder={d.folder} exists={d.exists} />
      </li>
    );
  }
  return (
    <li className="py-2.5 flex flex-col gap-1.5">
      <span className="flex items-center gap-2.5">
        <Avatar name="แผน" size="sm" />
        <button type="button" className="grow min-w-0 text-left cursor-pointer" onClick={() => setOpen((o) => !o)}>
          <span className="block font-semibold text-[13.5px]">แผน: {d.title}</span>
          <span className="block text-xs text-ink-2">
            {[when(d.created_at), d.model && `${d.model} · effort ${d.effort}`, open ? "ซ่อนแผน" : "ดูแผน"].filter(Boolean).join(" · ")}</span>
        </button>
      </span>
      {open && <Markdown text={d.plan} />}
      <PlanActions decisionId={d.id} />
    </li>
  );
}

/** One topic of the weekly review (D4, B7): the same buttons as its #สรุป message. The people topic
 *  is chosen person by person on the people page. */
function WeeklyRow({ d, onChange }: { d: Decision; onChange?: () => void }) {
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState("");
  const [answered, setAnswered] = useState(false); // then only what was done shows (the bell keeps the row)
  const act = async (a: string) => {
    setBusy(true);
    try { setSaid((await api.answerWeekly(d.id, a)).text); setAnswered(true); onChange?.(); } catch (e) { setSaid((e as Error).message); }
    setBusy(false);
  };
  return (
    <li className="py-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
      <Avatar name={d.label || "ท"} size="sm" />
      <span className="grow min-w-0 basis-48">
        <span className="block font-semibold text-[13.5px]">ทบทวนรายสัปดาห์ · {d.label}: {d.title}</span>
        <span className="block text-xs text-ink-2">{said || d.what}</span>
      </span>
      {!answered && d.topic === "people" && <Link to="/people" className="inline-flex items-center rounded-full border border-line-2 bg-panel hover:bg-panel-2 px-3 py-1 text-xs font-medium">เลือกรายคน</Link>}
      {!answered && (d.acts ?? []).map(([a, label]) => (
        <button key={a} type="button" disabled={busy} onClick={() => act(a)}
          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium cursor-pointer disabled:opacity-50 ${a === "reject" ? "border border-line-2 bg-panel hover:bg-panel-2" : "bg-accent text-accent-ink hover:bg-accent-strong"}`}>
          {label}</button>
      ))}
    </li>
  );
}
