from __future__ import annotations

from app.models import (
    ActionPlan,
    ExecutiveSummary,
    MeetingMetadata,
    PresentationCoaching,
    SelfCoaching,
    StakeholderProfile,
)

RESPONSIBLE_AI_NOTE = (
    "목적·우려 가설은 사실이 아니며, 인용과 확인 질문으로 당사자에게 검증해야 합니다."
)


def meeting_executive_summary(
    self_coaching: SelfCoaching,
    stakeholders: list[StakeholderProfile],
    action_plan: ActionPlan,
    schedule: MeetingMetadata | None = None,
) -> ExecutiveSummary:
    primary_stakeholder = stakeholders[0]
    schedule_prefix = (
        f"{schedule.date.isoformat()} {schedule.start_time.strftime('%H:%M')} "
        f"{schedule.timezone} 일정에서 "
        if schedule
        else ""
    )
    return ExecutiveSummary(
        headline=(
            f"{schedule_prefix}{self_coaching.speaker}는 논의를 전진시켰고, 다음 단계에서는 "
            f"{primary_stakeholder.speaker}의 핵심 조건을 명시적으로 확인하는 것이 우선입니다."
        ),
        priority_insights=[
            f"강점: {self_coaching.strengths[0].title}",
            f"개선: {self_coaching.improvements[0].title}",
            (
                f"핵심 긴장: {primary_stakeholder.core_perspective}"
            ),
        ],
        immediate_actions=[
            item.action for item in action_plan.action_items[:2]
        ],
        responsible_ai_note=RESPONSIBLE_AI_NOTE,
    )


def presentation_executive_summary(
    coaching: PresentationCoaching,
    schedule: MeetingMetadata | None = None,
) -> ExecutiveSummary:
    schedule_prefix = (
        f"{schedule.date.isoformat()} {schedule.start_time.strftime('%H:%M')} "
        f"{schedule.timezone} 발표는 "
        if schedule
        else f"{coaching.speaker}의 발표는 "
    )
    return ExecutiveSummary(
        headline=(
            f"{schedule_prefix}근거가 강점이며, 메시지를 더 짧게 구조화하고 "
            "질문에 결론부터 답하는 연습이 가장 중요합니다."
        ),
        priority_insights=[
            f"강점: {coaching.strengths[0].title}",
            f"개선: {coaching.improvements[0].title}",
            f"Q&A: {coaching.improvements[-1].title}",
        ],
        immediate_actions=coaching.next_presentation_checklist[:3],
        responsible_ai_note=(
            "텍스트에서 관찰되는 표현만 분석하며 음성 톤, 감정, 성격, "
            "카리스마를 추론하지 않습니다."
        ),
    )
