// W10 ตั้งค่า: models and effort per task, the secretary's clock, notification sounds, channels.
// Parts that arrive in later phases are shown greyed with their phase, as agreed in stage 2.
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router";
import { api, type Settings as S } from "../api";
import { when } from "../format";
import { Icon, type IconName } from "../icons";
import { Card, Chip, Phase, Seg, Spinner } from "../components/ui";
import { MailSettingsCard } from "./settings/MailSettings";
import { Reminders, RulesCard, useScheduleRules } from "./settings/ScheduleRules";

const MODEL_NAMES: Record<string, string> = { sonnet: "Sonnet", opus: "Opus" };

function Select({ value, options, onChange, label }: { value: string; options: string[]; onChange: (v: string) => void; label: string }) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}
      className="rounded-full border border-line-2 bg-panel px-2.5 py-1 text-sm cursor-pointer outline-none focus:border-accent">
      {options.map((o) => <option key={o} value={o}>{MODEL_NAMES[o] ?? o}</option>)}
    </select>
  );
}

function Row({ icon, title, sub, side, dim = false }: { icon: IconName; title: string; sub?: string; side?: React.ReactNode; dim?: boolean }) {
  return (
    <div className={`flex items-center gap-3 py-2 border-b border-line last:border-0 ${dim ? "opacity-60" : ""}`}>
      <Icon name={icon} className="text-ink-2" />
      <div className="flex flex-col grow min-w-0">
        <span className="text-sm font-medium">{title}</span>
        {sub && <span className="text-xs text-muted">{sub}</span>}
      </div>
      {side}
    </div>
  );
}

export function Settings() {
  const [s, setS] = useState<S | null>(null);
  const [note, setNote] = useState("");
  const rules = useScheduleRules(); // shared by กติกาตาราง and เตือนก่อนถึงกำหนด
  const load = useCallback(() => { api.settings().then(setS, (e) => setNote((e as Error).message)); }, []);
  useEffect(load, [load]);
  // /settings#rules and #mail (links from the schedule and people pages) scroll to their card
  const { hash } = useLocation();
  useEffect(() => {
    if (s && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [s, hash]);

  const setTask = async (task: string, model: string, effort: string) => {
    try {
      await api.setTask(task, model, effort);
      setNote("บันทึกแล้ว · ย้อนได้ที่หน้าสิ่งที่เลขาทำ");
    } catch (e) { setNote((e as Error).message); }
    load();
  };

  if (!s) return <Spinner label="กำลังโหลด…" />;
  const dc = s.discord;
  return (
    <div className="flex flex-col gap-3">
      {note && <p className="text-sm text-ink-2">{note}</p>}
      <div className="grid gap-4 xl:grid-cols-3 lg:grid-cols-2 items-start">
        <div className="flex flex-col gap-4">
          <Card title="ตัวเลือกโมเดล" flush>
            <table className="w-full text-sm">
              <thead><tr className="text-left text-muted border-y border-line">
                <th className="font-normal px-4 py-2">งาน</th><th className="font-normal px-2 py-2">ใช้</th><th className="font-normal px-2 py-2">effort</th>
              </tr></thead>
              <tbody>
                {s.tasks.map((t) => (
                  <tr key={t.task} className="border-b border-line">
                    <td className="px-4 py-2 font-semibold">{t.label}</td>
                    <td className="px-2 py-2"><Select label="โมเดล" value={t.model} options={s.models} onChange={(m) => setTask(t.task, m, t.effort)} /></td>
                    <td className="px-2 py-2"><Select label="effort" value={t.effort} options={s.efforts} onChange={(e) => setTask(t.task, t.model, e)} /></td>
                  </tr>
                ))}
                {s.planned_tasks.map((t) => (
                  <tr key={t.label} className={`border-b border-line last:border-0 ${t.phase ? "opacity-60" : ""}`}>
                    <td className={`px-4 py-2 ${t.phase ? "" : "font-semibold"}`}>{t.label}</td>
                    <td className="px-2 py-2">{t.model}</td>
                    <td className="px-2 py-2"><span className="font-mono text-xs mr-2">{t.effort}</span>{t.phase && <Phase phase={t.phase} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-4 py-3 text-xs text-muted">ถามตอบใช้ Sonnet ตอบเร็ว · วางแผนและสั่งงานใช้ Opus · Sonnet ตอบไม่พอ กด “ให้ Opus คิดต่อ” · effort ต่ำ = เร็วและประหยัด สูง = คิดลึกขึ้นแต่ใช้โทเคนมากขึ้น</p>
          </Card>
          <Card title="นาฬิกาเลขา">
            {s.clock.map((r) => (
              <Row key={r.id} icon="clock" title={r.when}
                sub={r.title + (r.active && r.enabled ? ` · ครั้งถัดไป ${when(r.next_run)}` : r.active ? " · ปิดอยู่" : "")} dim={!r.active || !r.enabled}
                side={r.active
                  ? <Seg options={[{ key: "on", label: "เปิด" }, { key: "off", label: "ปิด" }]} value={r.enabled ? "on" : "off"}
                      onChange={(v) => api.setRound(r.id, v === "on").then(load, (e) => setNote((e as Error).message))} />
                  : <Phase phase={r.phase} />} />
            ))}
            <p className="text-xs text-muted pt-2">เครื่องดับแล้วเปิดใหม่ เลขาทำรอบที่พลาดทันที (ครั้งเดียว ไม่ว่าพลาดกี่รอบ) · รอบใหม่ของแต่ละช่วงเริ่มแบบปิด คุณเปิดเองตอนทดสอบช่วงนั้น · ทุกการเปิดปิดอยู่ในหน้าบันทึกและย้อนกลับได้</p>
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card title="อนุมัติเอง" right={<Link to="/rules" className="text-xs font-semibold text-accent-strong hover:underline">แก้ที่สมุดกติกา →</Link>}>
            <div className="text-sm flex flex-col gap-1.5">
              <span>{s.jobs_rule.auto ? `โควตาสัปดาห์เหลือเกิน ${s.jobs_rule.line}% · ความเสี่ยงต่ำเท่านั้น` : "ปิดอยู่ · ทุกแผนงานเบื้องหลังถามคุณก่อน"}</span>
              <span>อายุการอนุมัติ {s.jobs_rule.approval_days} วัน เฉพาะแผนนั้น · งบโทเคนต่องาน เกินงบหยุดเสมอ</span>
              <span className="text-xs text-muted">ถ้าอ่านโควตา Pro ไม่ได้ ทุกแผนงานเบื้องหลังต้องขออนุมัติ · งานเสี่ยงสูงถามทุกครั้ง</span>
            </div>
          </Card>
          <Card title="เสียงแจ้งเตือน">
            <Row icon="bell" title="#ด่วน · #อนุมัติ" sub="ทุกข้อความ" side={<Chip tone="acc">เด้ง</Chip>} />
            <Row icon="bell" title="#สรุป · #ไอเดีย" sub="สรุปเช้า-เย็น · จัดกลุ่มไอเดีย" side={<Chip tone="acc">เด้ง</Chip>} />
            <Row icon="bell" title="#คุยกับเลขา" sub="ทุกคำตอบ" side={<Chip tone="acc">เด้ง</Chip>} />
            <p className="text-xs text-muted pt-2">ตามที่ตกลง: ทุกห้องเด้งเสียง · ตั้งในแอป Discord ของแต่ละเครื่อง: คลิกขวาที่เซิร์ฟเวอร์ → Notification Settings → All Messages · กลางคืนใช้โหมดห้ามรบกวนของมือถือได้</p>
          </Card>
          <Reminders {...rules} />
          <RulesCard {...rules} />
        </div>

        <div className="flex flex-col gap-4">
          <Card title="ช่องทางและบริการ">
            <Row icon="chat" title="Discord" sub={dc.connected ? `${dc.user} · ${dc.channels.join(" ")}` : dc.problem}
              side={dc.connected ? <Chip tone="ok">เชื่อมแล้ว</Chip> : <Chip tone="warn">{dc.configured ? "มีปัญหา" : "รอตั้งค่า"}</Chip>} />
            {s.google.map((g) => (
              <Row key={g.id} icon="mail" title={`Google · ${g.label}`}
                sub={g.connected ? [g.address, g.does].filter(Boolean).join(" · ") : g.problem}
                side={g.connected ? <Chip tone="ok">เชื่อมแล้ว</Chip> : <Chip tone="warn">รอเชื่อม</Chip>} />
            ))}
            {s.services.map((x) => (
              <Row key={x.name} icon={x.icon as IconName} title={x.name} sub={x.detail} dim side={<Phase phase={x.phase} />} />
            ))}
            {!dc.connected && <p className="text-xs text-muted pt-2">วิธีตั้งค่า Discord: docs/setup/discord.md</p>}
          </Card>
          <MailSettingsCard />
          <Card title="เปิดหน้าเว็บจาก">
            <Row icon="monitor" title="คอมเครื่องนี้" sub={window.location.host} side={<Chip tone="ok">ใช้อยู่</Chip>} />
            <Row icon="tablet" title="iPad" sub="ผ่าน Tailscale · my-pc:8000" dim side={<Phase phase="B8" />} />
            <p className="text-xs text-muted pt-2">ไม่เปิดสู่อินเทอร์เน็ต · เข้าได้เฉพาะเครื่องที่คุณเพิ่ม</p>
          </Card>
        </div>
      </div>
    </div>
  );
}
