from __future__ import annotations

import re
from collections import Counter

from app.models import (
    ActionItem,
    ActionPlan,
    Citation,
    CoachingInsight,
    SelfCoaching,
    StakeholderHypothesis,
    StakeholderProfile,
    TranscriptTurn,
)

REQUEST_WORDS = ("부탁", "필요", "해 주세요", "하면 좋", "원합니다", "확인", "정리")
CONCERN_WORDS = ("어렵", "걱정", "리스크", "문제", "부담", "늦", "부족", "불안")
DECISION_WORDS = ("결정", "합의", "진행", "확정", "하기로", "먼저")
QUESTION_WORDS = ("?", "까요", "나요", "인지", "어떻게")
DEADLINE_PATTERN = re.compile(
    r"(오늘|내일|이번 주|다음 주|월요일|화요일|수요일|목요일|금요일|"
    r"\d{1,2}월\s*\d{1,2}일|\d{1,2}일)"
)


def citation(turn: TranscriptTurn) -> Citation:
    return Citation(
        speaker=turn.speaker,
        quote=turn.text[:180],
        timestamp=turn.timestamp,
        source=turn.source,
    )


def pick(turns: list[TranscriptTurn], words: tuple[str, ...]) -> list[TranscriptTurn]:
    matches = [turn for turn in turns if any(word in turn.text for word in words)]
    return matches or turns[:1]


def analyze_self(
    turns: list[TranscriptTurn], self_speaker: str
) -> SelfCoaching:
    mine = [turn for turn in turns if turn.speaker == self_speaker]
    others = [turn for turn in turns if turn.speaker != self_speaker]
    question_turns = pick(mine, QUESTION_WORDS)
    action_turns = pick(mine, REQUEST_WORDS + DECISION_WORDS)
    longest = max(mine, key=lambda turn: len(turn.text))
    share = len(mine) / len(turns)

    strengths = [
        CoachingInsight(
            title="논의를 앞으로 움직이는 발화",
            observation=(
                "질문이나 실행 제안으로 대화가 다음 단계로 이어지도록 했습니다."
            ),
            evidence=[citation(question_turns[0])],
            next_behavior="다음 회의에서도 쟁점마다 확인 질문을 한 문장으로 남기세요.",
        ),
        CoachingInsight(
            title="구체적인 맥락 제공",
            observation="근거나 제약을 담은 발화가 논의의 기준점을 만들었습니다.",
            evidence=[citation(longest)],
            next_behavior="핵심 근거 뒤에 원하는 결정까지 짧게 연결해 보세요.",
        ),
    ]

    if share > 0.42:
        improvement_title = "발화 공간 균형"
        improvement_observation = (
            f"전체 {len(turns)}개 발화 중 {len(mine)}개를 말했습니다. "
            "설명 뒤에 다른 참여자의 관점을 먼저 확인하면 공동 소유감이 커집니다."
        )
        next_behavior = "두 문장 설명 후 한 번 질문하는 2:1 리듬을 시도하세요."
    else:
        improvement_title = "입장과 요청의 선명도"
        improvement_observation = (
            "핵심 관점은 보이지만 원하는 결정이나 지원을 더 직접적으로 말할 수 있습니다."
        )
        next_behavior = "발언을 '관찰-영향-요청' 세 문장으로 준비하세요."

    evidence_turn = action_turns[0] if action_turns else mine[0]
    response_turn = others[0]
    improvements = [
        CoachingInsight(
            title=improvement_title,
            observation=improvement_observation,
            evidence=[citation(evidence_turn)],
            next_behavior=next_behavior,
        ),
        CoachingInsight(
            title="상대 발언의 명시적 확인",
            observation=(
                "상대의 요청을 요약해 되돌려주면 가정과 사실을 더 명확히 분리할 수 있습니다."
            ),
            evidence=[citation(response_turn)],
            next_behavior=(
                f"'{response_turn.speaker}님의 요청은 …로 이해했는데 맞나요?'라고 확인하세요."
            ),
        ),
    ]

    return SelfCoaching(
        speaker=self_speaker,
        summary=(
            f"{self_speaker}의 발화 {len(mine)}개를 다른 참여자의 발화와 분리해 분석했습니다. "
            "아래 내용은 대화 행동 코칭이며 성격이나 감정에 대한 판단이 아닙니다."
        ),
        strengths=strengths,
        improvements=improvements,
    )


def analyze_stakeholders(
    turns: list[TranscriptTurn], self_speaker: str
) -> list[StakeholderProfile]:
    profiles: list[StakeholderProfile] = []
    speakers = list(dict.fromkeys(turn.speaker for turn in turns))

    for speaker in speakers:
        if speaker == self_speaker:
            continue
        speaker_turns = [turn for turn in turns if turn.speaker == speaker]
        request_turns = [
            turn
            for turn in speaker_turns
            if any(word in turn.text for word in REQUEST_WORDS)
        ]
        concern_turns = [
            turn
            for turn in speaker_turns
            if any(word in turn.text for word in CONCERN_WORDS)
        ]
        strongest = max(speaker_turns, key=lambda turn: len(turn.text))
        evidence_turn = (concern_turns or request_turns or [strongest])[0]

        explicit_requests = (
            [f'"{turn.text}"' for turn in request_turns[:2]]
            if request_turns
            else ["명시적으로 표현된 요청이 없습니다."]
        )
        concerns = (
            [f'"{turn.text}"' for turn in concern_turns[:2]]
            if concern_turns
            else ["명시적으로 표현된 우려가 없습니다."]
        )

        confidence = "높음" if request_turns and concern_turns else "중간"
        possible_goal = (
            f"{speaker}는 언급한 제약을 관리하면서 실행 가능한 합의를 "
            "확보하려는 것일 수 있습니다."
        )
        profiles.append(
            StakeholderProfile(
                speaker=speaker,
                core_perspective=possible_goal,
                explicit_requests=explicit_requests,
                concerns=concerns,
                hypotheses=[
                    StakeholderHypothesis(
                        possible_goal_or_concern=possible_goal,
                        confidence=confidence,
                        observed_cues=[evidence_turn.text],
                        citations=[citation(evidence_turn)],
                        confirmation_question=(
                            f"{speaker}님, 지금 가장 먼저 확인받고 싶은 기준이 "
                            "실행 가능성과 일정 중 어느 쪽인지 여쭤봐도 될까요?"
                        ),
                    )
                ],
            )
        )
    return profiles


def analyze_actions(turns: list[TranscriptTurn]) -> ActionPlan:
    decision_turns = [
        turn
        for turn in turns
        if any(word in turn.text for word in DECISION_WORDS)
    ]
    question_turns = [
        turn
        for turn in turns
        if any(word in turn.text for word in QUESTION_WORDS)
    ]
    action_candidates = [
        turn
        for turn in turns
        if any(word in turn.text for word in REQUEST_WORDS + DECISION_WORDS)
    ]
    if not action_candidates:
        action_candidates = turns[-2:]

    decisions = (
        [turn.text for turn in decision_turns[:4]]
        if decision_turns
        else ["명시적으로 확정된 결정이 없습니다. 후속 확인이 필요합니다."]
    )
    unresolved = (
        [turn.text for turn in question_turns[-4:]]
        if question_turns
        else ["성공 기준과 최종 승인자를 확인해야 합니다."]
    )

    counts = Counter(turn.speaker for turn in turns)
    action_items: list[ActionItem] = []
    for candidate in action_candidates[:4]:
        deadline_match = DEADLINE_PATTERN.search(candidate.text)
        action_items.append(
            ActionItem(
                owner=candidate.speaker,
                deadline=deadline_match.group(0) if deadline_match else "다음 회의 전 확인",
                action=candidate.text,
                evidence=[citation(candidate)],
            )
        )

    least_heard = min(counts, key=counts.get)
    return ActionPlan(
        decisions=decisions,
        unresolved_questions=unresolved,
        action_items=action_items,
        recommended_followups=[
            "회의 종료 후 결정·담당자·기한을 한 문단으로 공유하고 각 담당자의 확인을 받으세요.",
            f"발화가 상대적으로 적었던 {least_heard}에게 빠진 우려나 조건이 있는지 비동기로 확인하세요.",
            "가설로 표시된 이해관계자 목표는 확인 질문에 답을 받기 전까지 사실로 취급하지 마세요.",
        ],
    )
