from __future__ import annotations

from collections import Counter

from app.models import (
    Citation,
    PresentationCoaching,
    PresentationFinding,
    TranscriptTurn,
)

EVIDENCE_WORDS = ("예를", "데이터", "결과", "퍼센트", "%", "명", "건", "실험")
STRUCTURE_WORDS = ("먼저", "다음", "마지막", "결론", "핵심", "요약")
FILLER_WORDS = ("사실", "약간", "그냥", "그러니까", "아무튼", "뭐랄까")
QUESTION_WORDS = ("?", "까요", "나요", "왜", "어떻게")


def _citation(turn: TranscriptTurn) -> Citation:
    return Citation(
        speaker=turn.speaker,
        quote=turn.text[:180],
        timestamp=turn.timestamp,
        source=turn.source,
    )


def _finding(
    dimension: str,
    title: str,
    observation: str,
    turn: TranscriptTurn,
    rewritten_phrase: str,
    rehearsal_action: str,
) -> PresentationFinding:
    return PresentationFinding(
        dimension=dimension,
        title=title,
        observation=observation,
        evidence=[_citation(turn)],
        rewritten_phrase=rewritten_phrase,
        rehearsal_action=rehearsal_action,
    )


def analyze_presentation(
    turns: list[TranscriptTurn], presenter: str
) -> PresentationCoaching:
    mine = [turn for turn in turns if turn.speaker == presenter]
    others = [turn for turn in turns if turn.speaker != presenter]
    first = mine[0]
    longest = max(mine, key=lambda turn: len(turn.text))
    evidence_turns = [
        turn for turn in mine if any(word in turn.text for word in EVIDENCE_WORDS)
    ]
    structured_turns = [
        turn for turn in mine if any(word in turn.text for word in STRUCTURE_WORDS)
    ]
    filler_turns = [
        turn for turn in mine if any(word in turn.text for word in FILLER_WORDS)
    ]

    if evidence_turns:
        evidence_turn = evidence_turns[0]
        evidence_strength = _finding(
            "근거와 예시",
            "주장을 구체화하는 근거",
            "수치나 사례를 사용해 청중이 주장의 기준을 확인할 수 있습니다.",
            evidence_turn,
            f"핵심 근거는 '{evidence_turn.text}'입니다.",
            "주장마다 가장 강한 수치나 사례 하나만 표시해 리허설하세요.",
        )
    else:
        evidence_strength = _finding(
            "핵심 메시지",
            "주제의 직접적인 제시",
            "발표의 대상 주제를 첫 발화에서 드러냈습니다.",
            first,
            f"오늘 말씀드릴 핵심은 {first.text[:60]}입니다.",
            "첫 20초 안에 주제와 청중이 얻을 가치를 한 문장으로 말하세요.",
        )

    structure_turn = structured_turns[0] if structured_turns else mine[-1]
    structure_strength = _finding(
        "구조",
        "전환점이 보이는 설명",
        (
            "순서나 핵심을 나타내는 표현이 있어 청중이 현재 위치를 "
            "따라갈 단서를 제공합니다."
        ),
        structure_turn,
        "먼저 배경, 다음으로 근거, 마지막으로 요청을 말씀드리겠습니다.",
        "슬라이드 전환마다 '지금까지/다음은' 표지 문장을 소리 내어 연습하세요.",
    )

    filler_counts = Counter(
        word for turn in mine for word in FILLER_WORDS if word in turn.text
    )
    if filler_counts:
        filler, count = filler_counts.most_common(1)[0]
        filler_observation = (
            f"'{filler}' 표현이 {count}개 발화에서 관찰됩니다. "
            "텍스트에서 확인되는 반복이며 말투나 성격에 대한 판단은 아닙니다."
        )
    else:
        filler = ""
        filler_observation = (
            "반복 필러보다 한 문장에 여러 메시지가 함께 들어간 부분을 줄이면 "
            "핵심이 더 선명해집니다."
        )
    concision = _finding(
        "명료성·간결성",
        "한 문장, 한 메시지",
        filler_observation,
        filler_turns[0] if filler_turns else longest,
        (
            longest.text.replace(filler, "").strip()[:90]
            if filler
            else f"핵심은 {longest.text[:70]}입니다."
        ),
        "긴 발화를 15초 단위로 녹음하고 한 문장에 주장 하나만 남기세요.",
    )

    questions = [
        turn for turn in others if any(word in turn.text for word in QUESTION_WORDS)
    ]
    if questions:
        question = questions[0]
        question_index = turns.index(question)
        later_answers = [
            turn for turn in mine if turns.index(turn) > question_index
        ]
        answer_evidence = later_answers[0] if later_answers else question
        answer_observation = (
            "질문 뒤 답변에서 결론을 먼저 말하고 근거를 붙이면 대응이 더 직접적입니다."
        )
        rewritten = (
            f"결론부터 말씀드리면 그렇습니다. 근거는 "
            f"{answer_evidence.text[:60]}입니다."
        )
    else:
        answer_evidence = mine[-1]
        answer_observation = (
            "질문·반론 대응 장면이 없어 실제 Q&A 역량은 판단할 수 없습니다. "
            "예상 반론을 리허설에 추가할 수 있습니다."
        )
        rewritten = "좋은 질문입니다. 결론, 근거, 다음 행동 순서로 답하겠습니다."
    q_and_a = _finding(
        "질문·반론 대응",
        "결론 우선 답변",
        answer_observation,
        answer_evidence,
        rewritten,
        "가장 어려운 예상 질문 세 개에 30초 결론-근거 답변을 준비하세요.",
    )

    return PresentationCoaching(
        speaker=presenter,
        overview=(
            f"{presenter}의 발표 발화 {len(mine)}개를 구조, 명료성, 간결성, "
            "근거·예시, 질문 대응 기준으로 분석했습니다. 음성 톤이나 성격은 평가하지 않습니다."
        ),
        strengths=[evidence_strength, structure_strength],
        improvements=[concision, q_and_a],
        next_presentation_checklist=[
            "첫 20초에 문제, 청중 가치, 발표 순서를 말한다.",
            "각 핵심 주장에 수치나 사례 하나를 연결한다.",
            "반복 표현을 지우고 한 문장에 메시지 하나만 남긴다.",
            "예상 질문 세 개에 결론-근거-다음 행동 순으로 답한다.",
            "마지막 30초에 요청 또는 다음 단계를 분명히 말한다.",
        ],
    )
