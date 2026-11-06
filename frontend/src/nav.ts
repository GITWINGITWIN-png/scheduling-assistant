// The left menu (stage 2's NAV), with the phase each page arrives in.
// `ready` pages exist now; the others open a "มาในช่วง Bx" page that says what they'll hold.
import type { IconName } from "./icons";

export type NavItem = {
  path: string; label: string; icon: IconName; screen: string; phase: string; ready: boolean; about: string;
  count?: "people" | "decisions" | "jobs" | "projects"; // which of /api/status's counts shows next to it (red; projects: grey)
};

export const NAV: (NavItem | { group: string })[] = [
  { path: "/", label: "วันนี้", icon: "home", screen: "W1", phase: "B4", ready: true, count: "decisions",
    about: "ทุกอย่างของวันนี้ในหน้าเดียว: ตารางเทียบที่ทำจริง เรื่องที่รอคุณ เรื่องสำคัญ งานเบื้องหลัง ข่าวโปรเจค" },
  { path: "/people", label: "คนและอีเมล", icon: "people", screen: "W2", phase: "B2", ready: true, count: "people",
    about: "ทะเบียนคน 3 ระดับพร้อมวันหมดอายุและโน้ตเหตุผล สรุปรายคน เรื่องค้าง" },
  { path: "/projects", label: "โปรเจค", icon: "folder", screen: "W3", phase: "B5", ready: true, count: "projects", about: "" },
  { path: "/jobs", label: "งานเบื้องหลัง", icon: "jobs", screen: "W4", phase: "B5", ready: true, count: "jobs", about: "" },
  { path: "/schedule", label: "ตาราง", icon: "calendar", screen: "W5", phase: "B3", ready: true,
    about: "ตารางสัปดาห์: นัด เดดไลน์ บล็อกงาน ที่ทำจริง ซิงก์กับ Google Calendar" },
  { path: "/ideas", label: "ไอเดีย", icon: "idea", screen: "W6", phase: "B6", ready: true,
    about: "คลังไอเดียเป็นกลุ่ม · กลุ่มที่โตพอเสนอเป็นโปรเจคหรืองาน" },
  { path: "/time", label: "การใช้เวลา", icon: "chart", screen: "W7", phase: "B6", ready: false,
    about: "เวลาต่อวันตามหมวดและโปรเจคจาก ActivityWatch ผ่านตัวกรองความเป็นส่วนตัว" },
  { group: "ระบบ" },
  { path: "/rules", label: "สมุดกติกา", icon: "book", screen: "W8", phase: "B5", ready: true, about: "" },
  { path: "/log", label: "สิ่งที่เลขาทำ", icon: "log", screen: "W9", phase: "B1", ready: true, about: "" },
  { path: "/settings", label: "ตั้งค่า", icon: "gear", screen: "W10", phase: "B1", ready: true, about: "" },
];

export const PAGES = NAV.filter((n): n is NavItem => "path" in n);
