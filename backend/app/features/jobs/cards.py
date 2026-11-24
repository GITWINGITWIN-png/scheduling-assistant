"""Background plans in Discord: the D5 card in #Approval ("Background plan, needs your answer") with
the buttons Approve 3 days, Revise plan and Decline, and a menu to change the model and effort before you approve
(the budget follows the effort). The same plan waits in the bell and on the jobs page (W4):
answering in any of them has the same result.
"""

from __future__ import annotations

import discord

from app.connectors import discord_bot as dc
from app.core.db import session
from app.core.tables import Action, Decision
from app.core.timefmt import thai_datetime
from app.features.actions_discord import UndoButton, after_undo
from app.features.jobs import plan as plans
from app.features.jobs.tables import Job

COMBOS = (("sonnet", "low"), ("sonnet", "medium"), ("sonnet", "high"), ("opus", "medium"), ("opus", "high"), ("opus", "xhigh"))
ACTS = {"approve": ("อนุมัติ 3 วัน", discord.ButtonStyle.success), "edit": ("แก้แผน", discord.ButtonStyle.secondary),
        "reject": ("ไม่เอา", discord.ButtonStyle.danger)}


def k(tokens: int) -> str:
    return f"{tokens / 1000:.0f}k"


def _ready() -> bool:
    return dc.bot.ready_event.is_set() and not dc.bot.is_closed()


def _via(message: discord.Message | None) -> tuple[str, str]:
    return ("#อนุมัติ", message.jump_url if message else "")


def card(job: Job, decision_id: int) -> tuple[discord.Embed, discord.ui.View]:
    risks = plans.names(job.risks)
    fields = [("ค้างที่", job.stuck_at or job.note or "—", True),
              ("โมเดล · งบ", f"{job.model.capitalize()} · {job.effort} · {k(job.budget)} โทเคน", True),
              ("แผน", " · ".join(f"{i} {s}" for i, s in enumerate(job.steps, 1))[:1000], False),
              ("ความเสี่ยง", f"สูง: {' · '.join(risks)}" if risks else "ต่ำ", True),
              ("กฎ", f"ไม่ผ่าน → ถามคุณ · {job.rule_why}", True)]
    embed = dc.embed(f"{job.project}: {job.title}", job.why, tone="warn", author="แผนงานเบื้องหลัง · ต้องถามคุณ", fields=fields,
                     footer="อนุมัติแล้วใช้ได้ 3 วัน เฉพาะแผนนี้ · ทำบน branch แยก ไม่ push")
    view = dc.buttons(*(JobButton(decision_id, a) for a in ACTS), EffortMenu(decision_id, job))
    return embed, view


class JobButton(discord.ui.DynamicItem[discord.ui.Button], template=r"job:(?P<id>\d+):(?P<act>approve|edit|reject)"):
    def __init__(self, decision_id: int, act: str) -> None:
        self.decision_id, self.act = decision_id, act
        label, style = ACTS[act]
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"job:{decision_id}:{act}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]), match["act"])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("ปุ่มนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        if self.act == "edit":
            await interaction.response.send_modal(EditJobModal(self.decision_id))
            return
        try:
            job, action_id = plans.answer(self.decision_id, self.act == "approve", via=_via(interaction.message))
        except plans.PlanError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        done = (f"✅ อนุมัติแล้ว ใช้ได้ถึง {thai_datetime(job.approved_until)} · เลขาเริ่มในช่วง 01:00–06:00 หรือกดทำเลยที่หน้างานเบื้องหลัง"
                if self.act == "approve" else "ไม่เอาแผนนี้ · ขั้นนี้จะไม่กลับมาเอง (กดทำต่อที่หน้าโปรเจคได้เสมอ)")
        await interaction.response.edit_message(content=done, view=dc.buttons(UndoButton(action_id)))


class EffortMenu(discord.ui.DynamicItem[discord.ui.Select], template=r"jobfx:(?P<id>\d+)"):
    def __init__(self, decision_id: int, job: Job | None = None) -> None:
        self.decision_id = decision_id
        options = []
        for model, effort in COMBOS:
            label = f"{model.capitalize()} · {effort}"
            if job is not None and job.effort in plans.EFFORT_COST:
                label += f" ≈ {k(plans.budget_for(plans.rescale(job.estimate, job.effort, effort)))}"
            options.append(discord.SelectOption(label=label, value=f"{model}:{effort}",
                                                default=job is not None and (job.model, job.effort) == (model, effort)))
        super().__init__(discord.ui.Select(placeholder="ปรับโมเดลและ effort (งบเปลี่ยนตาม)", options=options,
                                           custom_id=f"jobfx:{decision_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not dc.bot.is_owner(interaction.user):
            await interaction.response.send_message("เมนูนี้สำหรับเจ้าของเลขาเท่านั้น", ephemeral=True)
            return
        model, effort = self.item.values[0].split(":")
        with session() as s:
            d = s.get(Decision, self.decision_id)
            job_id = d.detail.get("job_id") if d is not None and d.status == "pending" else None
        if job_id is None:
            await interaction.response.send_message("แผนนี้ตัดสินไปแล้ว", ephemeral=True)
            return
        try:
            job = plans.set_effort(job_id, model, effort, via=_via(interaction.message))
        except plans.PlanError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        embed, view = card(job, self.decision_id)
        await interaction.response.edit_message(embed=embed, view=view)


class EditJobModal(discord.ui.Modal, title="แก้แผนงานเบื้องหลัง"):
    change = discord.ui.TextInput(label="อยากให้แก้ตรงไหน", style=discord.TextStyle.paragraph, max_length=1000,
                                  placeholder="เช่น ไม่ต้องลงแพ็กเกจใหม่ ใช้ของที่มีอยู่")

    def __init__(self, decision_id: int) -> None:
        super().__init__()
        self.decision_id = decision_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            verdict = await plans.revise(self.decision_id, self.change.value, via=_via(interaction.message))
        except Exception as exc:  # a PlanError, or Claude unreachable
            await interaction.followup.send(f"แก้แผนไม่สำเร็จ: {exc}", ephemeral=True)
            return
        if interaction.message:
            await interaction.message.edit(content="✏️ แก้แผนแล้ว · แผนใหม่ส่งตามมา", view=None)
        await interaction.followup.send("แผนใหม่ " + ("ผ่านกฎแล้ว รอทำ" if verdict.go else "ส่งมาในห้องนี้แล้ว รอคุณตอบ"),
                                        ephemeral=True)


async def ask_job(job_id: int, decision_id: int) -> None:
    """plans.ASKED hook: a background plan that has to ask you."""
    if not _ready():
        return
    with session() as s:
        job = s.get(Job, job_id)
        s.expunge(job)
    embed, view = card(job, decision_id)
    row, _ = await dc.bot.send("approve", embed=embed, view=view, kind="job", ref=f"decision:{decision_id}",
                               text_copy=f"แผนงานเบื้องหลัง {job.project}: {job.title}")
    with session() as s:
        s.get(Decision, decision_id).message_id = row.id


async def _reopened(a: Action) -> tuple[str, discord.ui.View | None]:
    """After undoing an answer: the plan waits for you again, with its buttons."""
    decision_id = (a.undo or {}).get("decision_id")
    with session() as s:
        d = s.get(Decision, decision_id)
        job = s.get(Job, (d.detail or {}).get("job_id")) if d else None
        if job is not None:
            s.expunge(job)
    if job is None or job.status != "asking":
        return "↩️ ย้อนกลับแล้ว", None
    return f"↩️ ย้อนกลับแล้ว · แผน “{job.title}” รอคุณตัดสินอีกครั้ง", card(job, decision_id)[1]


def setup() -> None:
    dc.register_buttons(JobButton, EffortMenu)
    if ask_job not in plans.ASKED:
        plans.ASKED.append(ask_job)
    after_undo["job.approve"] = after_undo["job.reject"] = _reopened
