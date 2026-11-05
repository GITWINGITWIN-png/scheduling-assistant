// A page from the agreed design that arrives in a later phase: says what it will hold, and when.
import { Link } from "react-router";
import { Icon } from "../icons";
import type { NavItem } from "../nav";
import { Card, Phase } from "../components/ui";

export function Soon({ page }: { page: NavItem }) {
  return (
    <div className="max-w-2xl flex flex-col gap-4">
      <Card>
        <div className="flex items-start gap-4 pt-4">
          <span className="size-12 rounded-full bg-accent-soft text-accent-strong grid place-items-center shrink-0"><Icon name={page.icon} size={24} /></span>
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2"><h2 className="text-lg font-semibold">{page.label}</h2><Phase phase={page.phase} /></div>
            <p className="text-ink-2">หน้านี้มาในช่วง {page.phase}: {page.about}</p>
            <p className="text-xs text-muted">หน้าจอ {page.screen} ตามที่ตกลงในขั้น 2 · ลำดับงานทั้งหมดอยู่ใน docs/plan-v2/PLAN.md</p>
          </div>
        </div>
      </Card>
      <Card title="ตอนนี้ (B1) ใช้ได้แล้ว">
        <ul className="flex flex-col gap-2 text-sm">
          <li className="flex gap-2"><Icon name="search" size={16} className="text-accent mt-0.5" />ถามเลขาที่ช่องด้านบน (กด <kbd className="border border-line-2 rounded px-1 text-xs">/</kbd>) หรือในแชทส่วนตัวของ Discord</li>
          <li className="flex gap-2"><Icon name="log" size={16} className="text-accent mt-0.5" /><Link to="/log" className="text-accent-strong hover:underline">สิ่งที่เลขาทำ</Link> ทุกอย่างพร้อมที่มาและปุ่มย้อนกลับ</li>
          <li className="flex gap-2"><Icon name="gear" size={16} className="text-accent mt-0.5" /><Link to="/settings" className="text-accent-strong hover:underline">ตั้งค่า</Link> โมเดลและ effort ต่องาน นาฬิกาเลขา ช่องทาง</li>
          <li className="flex gap-2"><Icon name="palette" size={16} className="text-accent mt-0.5" />เปลี่ยนธีมสีที่ปุ่มจานสีด้านบน</li>
        </ul>
      </Card>
    </div>
  );
}
