// One request that waits for you, as the plan's W1 "รอคุณตัดสิน" draws it: an avatar, what it is,
// one line under it, and its buttons. The bell and the today page show the same rows; answering in
// either place (or in #อนุมัติ) has the same result (B4: เรื่องที่รอคุณตัดสินรวมที่เดียว).
import { useState } from "react";
import type { Decision } from "../api";
import { when } from "../format";
import { AppointmentActions, CourseActions } from "./Bell";
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
