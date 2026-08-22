const state = {
  samples: [],
  fixtures: [],
  productMode: "meeting-insight",
  selectedSpeaker: "",
  result: null,
  files: [],
  meetings: [],
  calendarMonth: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  selectedDate: "",
  db: null,
  analysisController: null,
};
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");
const formatBytes = (bytes) => bytes < 1024 * 1024
  ? `${(bytes / 1024).toFixed(1)} KB`
  : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
const DISPLAY_LABELS = {
  complete: "완료",
  completed: "완료",
  running: "실행 중",
  failed: "실패",
  needs_review: "확인 필요",
  confirmation_needed: "확인 필요",
  high: "높음",
  medium: "중간",
  low: "낮음",
};
const displayLabel = (value) => DISPLAY_LABELS[value] || value;

const PIPELINES = {
  "meeting-insight": {
    title: "회의 맥락을 세 관점으로 이어서 분석합니다",
    helper: "나의 대화 행동과 다른 참여자의 명시적 요구·가설을 분리하고 후속 행동을 만듭니다.",
    speakerLabel: "나는 어떤 화자인가요?",
    stages: [
      ["self-coach", "SelfCoachAgent", "나의 발화만 분리"],
      ["stakeholder", "StakeholderAgent", "요청과 가설 분리"],
      ["action-planner", "ActionPlannerAgent", "후속 행동 종합"],
    ],
  },
  "presentation-coach": {
    title: "발표를 구조·표현·리허설 순서로 개선합니다",
    helper: "선택한 발표자의 구조, 명료성, 근거, 반복 표현과 Q&A를 텍스트 근거로 코칭합니다.",
    speakerLabel: "발표자는 어떤 화자인가요?",
    stages: [
      ["presentation-structure", "PresentationStructureAgent", "구조와 근거 점검"],
      ["presentation-clarity", "PresentationClarityAgent", "명료성·반복·Q&A"],
      ["presentation-rehearsal", "PresentationRehearsalAgent", "리허설 계획 종합"],
    ],
  },
};
async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}을 불러오지 못했습니다.`);
  return response.json();
}

async function initialize() {
  const [samples, fixtures, runtime] = await Promise.all([
    fetchJson("/api/samples"),
    fetchJson("/api/fixtures"),
    fetchJson("/api/runtime"),
  ]);
  state.samples = samples;
  state.fixtures = fixtures;
  $("#runtime-status").textContent = runtime.live_available
    ? "AI 분석 준비 완료"
    : "AI 심층 분석 준비 중 — 현재 분석을 시작할 수 없습니다.";
  $("#analyze").disabled = !runtime.live_available;
  $("#speech-status").textContent = runtime.speech_available
    ? "Azure Speech가 준비되었습니다. MP3를 전사한 뒤 화자 라벨을 확인하세요."
    : "현재 Azure Speech 비밀 설정이 없어 MP3 전사는 사용할 수 없습니다.";
  $("#event-timezone").value = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Seoul";
  renderFixtures();
  setProductMode("meeting-insight");
  await initializeCalendar();
}

function filteredSamples() {
  return state.samples.filter((sample) => sample.product_mode === state.productMode);
}

function renderSampleOptions() {
  const samples = filteredSamples();
  $("#sample-select").innerHTML = samples
    .map((sample) => `<option value="${escapeHtml(sample.id)}">${escapeHtml(sample.title)}</option>`)
    .join("");
  $("#sample-description").textContent = samples[0]?.description || "";
}

function setProductMode(mode) {
  state.productMode = mode;
  const config = PIPELINES[mode];
  $("#mode-helper").textContent = config.helper;
  $("#speaker-label").textContent = config.speakerLabel;
  $("#pipeline-title").textContent = config.title;
  $(".pipeline").innerHTML = config.stages.map((stage, index) => `
    ${index ? '<div class="connector" aria-hidden="true"></div>' : ""}
    <article class="agent-step" data-stage="${stage[0]}">
      <span class="step-number">${index + 1}</span>
      <div><h3>${stage[1]}</h3><p>${stage[2]}</p><small>대기 중</small></div>
    </article>`).join("");
  renderSampleOptions();
  clearResults();
}

function applySample(sample) {
  $("#sample-select").value = sample.id;
  $("#sample-description").textContent = sample.description;
  $("#transcript").value = sample.transcript;
  updateCount();
  renderSpeakers(sample.speakers, sample.recommended_self);
  clearResults();
}

function renderSpeakers(speakers, selected = speakers[0]) {
  state.selectedSpeaker = selected || "";
  $("#speaker-options").innerHTML = speakers.map((speaker) => `
    <label class="speaker-option">
      <input type="radio" name="speaker" value="${escapeHtml(speaker)}"
        ${speaker === selected ? "checked" : ""}>
      <span>${escapeHtml(speaker)}</span>
    </label>`).join("");
  document.querySelectorAll('input[name="speaker"]').forEach((input) => {
    input.addEventListener("change", (event) => { state.selectedSpeaker = event.target.value; });
  });
}

function detectSpeakers() {
  const speakers = [];
  for (const line of $("#transcript").value.split(/\r?\n/)) {
    const match = line.match(/^\s*(?:\[\d{1,2}:\d{2}(?::\d{2})?\]|\d{1,2}:\d{2}(?::\d{2})?)?\s*([A-Za-z가-힣][A-Za-z0-9가-힣 _-]{0,29})\s*[:：]/);
    if (match && !speakers.includes(match[1].trim())) speakers.push(match[1].trim());
  }
  renderSpeakers(
    speakers,
    speakers.includes(state.selectedSpeaker) ? state.selectedSpeaker : speakers[0],
  );
}

function updateCount() {
  $("#character-count").textContent = `${$("#transcript").value.length.toLocaleString()} / 50,000`;
}

function renderFixtures() {
  $("#fixture-list").innerHTML = state.fixtures.map((fixture) => `
    <article class="fixture-card">
      <strong>${escapeHtml(fixture.name)} · ${escapeHtml(fixture.format)}</strong>
      <span>${escapeHtml(fixture.description)}</span>
      <div class="fixture-actions">
        <button class="secondary-button load-fixture" type="button" data-id="${fixture.id}">불러오기</button>
        <a href="${fixture.download_url}" download>다운로드</a>
      </div>
    </article>`).join("");
  document.querySelectorAll(".load-fixture").forEach((button) => {
    button.addEventListener("click", () => loadFixture(button.dataset.id));
  });
}

async function loadFixture(id) {
  const fixture = state.fixtures.find((item) => item.id === id);
  const response = await fetch(fixture.download_url);
  const blob = await response.blob();
  const file = new File([blob], fixture.filename, { type: blob.type });
  state.files = [file];
  document.querySelector(`input[name="product-mode"][value="${fixture.product_mode}"]`).click();
  renderFileQueue();
  await extractFiles();
}

function addFiles(fileList) {
  const incoming = [...fileList];
  if (state.files.length + incoming.length > 5) {
    showError("파일은 최대 5개까지 선택할 수 있습니다.");
    return;
  }
  state.files.push(...incoming);
  renderFileQueue();
}

function renderFileQueue(statuses = {}) {
  $("#file-queue").innerHTML = state.files.map((file, index) => {
    const status = statuses[file.name] || { label: "추출 대기", type: "" };
    return `<li class="file-item">
      <div><strong>${escapeHtml(file.name)}</strong>
        <div class="file-meta">${escapeHtml(file.type || "유형 미지정")} · ${formatBytes(file.size)}</div>
      </div>
      <span class="file-status ${status.type}">${escapeHtml(status.label)}</span>
      <button class="text-button remove-file" data-index="${index}" type="button" aria-label="${escapeHtml(file.name)} 제거">제거</button>
    </li>`;
  }).join("");
  document.querySelectorAll(".remove-file").forEach((button) => {
    button.addEventListener("click", () => {
      state.files.splice(Number(button.dataset.index), 1);
      renderFileQueue();
    });
  });
  $("#extract-files").disabled = state.files.length === 0;
}

async function extractFiles() {
  if (!state.files.length) return;
  $("#error-box").hidden = true;
  const statuses = Object.fromEntries(state.files.map((file) => [
    file.name, { label: "추출 중…", type: "" },
  ]));
  renderFileQueue(statuses);
  const formData = new FormData();
  state.files.forEach((file) => formData.append("files", file));
  try {
    const response = await fetch("/api/extract/batch", { method: "POST", body: formData });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "파일 추출에 실패했습니다.");
    for (const item of body.files) {
      statuses[item.filename] = item.status === "complete"
        ? { label: item.message, type: "" }
        : { label: item.error, type: "error" };
    }
    renderFileQueue(statuses);
    if (body.combined_transcript) {
      $("#transcript").value = body.combined_transcript;
      updateCount();
      detectSpeakers();
    }
    if (!body.successful_files) showError("추출에 성공한 파일이 없습니다.");
  } catch (error) {
    showError(error.message);
  }
}

function setStage(stage, status, detail) {
  const element = document.querySelector(`[data-stage="${stage}"]`);
  if (!element) return;
  element.classList.remove("running", "complete");
  element.classList.add(status);
  element.querySelector("small").textContent = detail;
}

function resetPipeline() {
  document.querySelectorAll(".agent-step").forEach((step) => {
    step.classList.remove("running", "complete");
    step.querySelector("small").textContent = "대기 중";
  });
}

function citationHtml(item) {
  const time = item.timestamp ? `[${escapeHtml(item.timestamp)}] ` : "";
  const source = item.source ? `<span class="source-chip">${escapeHtml(item.source)}</span> ` : "";
  return `<blockquote class="evidence">${source}${time}<strong>${escapeHtml(item.speaker)}</strong> · “${escapeHtml(item.quote)}”</blockquote>`;
}

function listHtml(items) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function executiveHtml(summary, modeLabel, metrics) {
  return `<section class="executive-summary" aria-labelledby="executive-title">
    <div class="label-row"><div><p class="kicker">EXECUTIVE FIRST</p><h3 id="executive-title">한눈에 보는 핵심</h3></div>
      <span class="badge">${escapeHtml(modeLabel)}</span></div>
    <p class="executive-headline">${escapeHtml(summary.headline)}</p>
    <div class="coverage-strip">${metrics.map((metric) => `<span><strong>${metric.value}</strong>${escapeHtml(metric.label)}</span>`).join("")}</div>
    <div class="summary-columns">
      <div><strong>우선순위 인사이트</strong>${listHtml(summary.priority_insights)}</div>
      <div><strong>지금 할 일</strong>${listHtml(summary.immediate_actions)}</div>
    </div>
    <p class="rai-note">책임 있는 AI · ${escapeHtml(summary.responsible_ai_note)}</p>
  </section>`;
}

function agentProofHtml(result) {
  return `<section class="agent-proof" aria-label="실행된 AI 에이전트">
    <div><strong>${escapeHtml(result.mode_label)}</strong><small>전문가 Agent 라우팅 · 실제 실행 결과</small></div>
    ${result.pipeline.map((stage) => `<span><strong>${escapeHtml(stage.name)}</strong><small>${escapeHtml(displayLabel(stage.status))}</small></span>`).join("")}
  </section>`;
}

function getSchedule(requireComplete = true) {
  const values = {
    title: $("#event-title").value.trim(),
    date: $("#event-date").value,
    start_time: $("#event-time").value,
    duration_minutes: Number($("#event-duration").value || 60),
    timezone: $("#event-timezone").value.trim() || "Asia/Seoul",
    location: $("#event-location").value.trim() || null,
    purpose: $("#event-purpose").value.trim() || null,
  };
  const hasAny = values.title || values.date || values.start_time;
  if (!hasAny) return null;
  if (requireComplete && (!values.title || !values.date || !values.start_time)) {
    throw new Error("캘린더를 사용하려면 제목, 날짜, 시작 시간을 모두 입력하세요.");
  }
  return values;
}

function dateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function openMeetingDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("meeting-mirror-calendar", 1);
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore("meetings", { keyPath: "id" });
      store.createIndex("date", "date");
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function dbOperation(mode, operation) {
  return new Promise((resolve, reject) => {
    const transaction = state.db.transaction("meetings", mode);
    const store = transaction.objectStore("meetings");
    const request = operation(store);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function initializeCalendar() {
  state.db = await openMeetingDatabase();
  state.meetings = await dbOperation("readonly", (store) => store.getAll());
  if (!state.meetings.length) {
    const today = new Date();
    const examples = [
      { offset: 1, title: "제품 피치 리허설", time: "10:00", duration: 45, location: "온라인", purpose: "핵심 메시지와 Q&A 점검" },
      { offset: 3, title: "스프린트 계획", time: "14:00", duration: 60, location: "회의실 A", purpose: "출시 범위와 담당자 확정" },
      { offset: 8, title: "고객 요구사항 리뷰", time: "11:30", duration: 50, location: "화상 회의", purpose: "예산과 일정 우선순위 확인" },
    ].map((item, index) => {
      const date = new Date(today);
      date.setDate(today.getDate() + item.offset);
      return {
        id: `example-${index + 1}`,
        title: item.title,
        date: dateKey(date),
        start_time: item.time,
        duration_minutes: item.duration,
        timezone: $("#event-timezone").value,
        location: item.location,
        purpose: item.purpose,
        status: "예시",
        example: true,
        transcript: null,
        analysis: null,
      };
    });
    for (const record of examples) {
      await dbOperation("readwrite", (store) => store.put(record));
    }
    state.meetings = examples;
  }
  state.selectedDate = dateKey(new Date());
  renderCalendar();
}

function renderCalendar() {
  const month = state.calendarMonth;
  $("#calendar-month").textContent = new Intl.DateTimeFormat("ko-KR", {
    year: "numeric", month: "long",
  }).format(month);
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = new Date(first);
  start.setDate(1 - first.getDay());
  const cells = [];
  for (let index = 0; index < 42; index += 1) {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    const key = dateKey(date);
    const count = state.meetings.filter((meeting) => meeting.date === key).length;
    const classes = [
      "calendar-day",
      date.getMonth() !== month.getMonth() ? "outside" : "",
      key === state.selectedDate ? "selected" : "",
      count ? "has-events" : "",
    ].filter(Boolean).join(" ");
    cells.push(`<button type="button" class="${classes}" data-date="${key}" role="gridcell"
      aria-label="${key}, 일정 ${count}개"><strong>${date.getDate()}</strong>${count ? `<small>${count}개</small>` : ""}</button>`);
  }
  $("#calendar-grid").innerHTML = cells.join("");
  document.querySelectorAll(".calendar-day").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedDate = button.dataset.date;
      $("#event-date").value = state.selectedDate;
      renderCalendar();
    });
  });
  renderAgenda();
}

function renderAgenda() {
  const meetings = state.meetings
    .filter((meeting) => meeting.date === state.selectedDate)
    .sort((a, b) => a.start_time.localeCompare(b.start_time));
  const selected = new Date(`${state.selectedDate}T00:00:00`);
  const heading = new Intl.DateTimeFormat("ko-KR", {
    month: "long", day: "numeric", weekday: "short",
  }).format(selected);
  $("#day-agenda").innerHTML = `<strong>${heading} 일정</strong>${meetings.length
    ? meetings.map((meeting) => `<article class="agenda-card ${meeting.example ? "example" : ""}">
        <strong>${escapeHtml(meeting.start_time)} · ${escapeHtml(meeting.title)}</strong>
        <span>${escapeHtml(meeting.location || "장소 미정")} · ${escapeHtml(meeting.purpose || "목적 미입력")}</span>
        <span>상태: ${escapeHtml(meeting.status || "예정")}${meeting.example ? " · 예시" : ""}</span>
        <div class="agenda-actions">
          <button class="secondary-button load-meeting" data-id="${meeting.id}" type="button">불러오기/수정</button>
          <button class="secondary-button toggle-meeting" data-id="${meeting.id}" type="button">${meeting.status === "확정" ? "후보로 변경" : "확정하기"}</button>
          <button class="text-button delete-meeting" data-id="${meeting.id}" type="button">삭제</button>
        </div>
      </article>`).join("")
    : "<p class=\"muted\">저장된 일정이 없습니다.</p>"}`;
  document.querySelectorAll(".load-meeting").forEach((button) => {
    button.addEventListener("click", () => loadMeeting(button.dataset.id));
  });
  document.querySelectorAll(".delete-meeting").forEach((button) => {
    button.addEventListener("click", () => deleteMeeting(button.dataset.id));
  });
  document.querySelectorAll(".toggle-meeting").forEach((button) => {
    button.addEventListener("click", () => toggleMeetingStatus(button.dataset.id));
  });
  renderMeetingArchive();
}

function renderMeetingArchive() {
  const archived = state.meetings
    .filter((meeting) => meeting.transcript || meeting.analysis)
    .sort((a, b) => `${b.date}${b.start_time}`.localeCompare(`${a.date}${a.start_time}`));
  $("#meeting-archive-list").innerHTML = archived.length
    ? archived.map((meeting) => `<div class="archive-row">
        <span><strong>${escapeHtml(meeting.title)}</strong><br><small>${escapeHtml(meeting.date)} · ${escapeHtml(meeting.status)}</small></span>
        <span><button class="text-button load-archive" data-id="${meeting.id}" type="button">열기</button>
        <button class="text-button delete-meeting" data-id="${meeting.id}" type="button">삭제</button></span>
      </div>`).join("")
    : "<p class=\"muted\">저장에 동의한 회의 분석이 없습니다.</p>";
  document.querySelectorAll(".load-archive").forEach((button) => {
    button.addEventListener("click", () => loadMeeting(button.dataset.id));
  });
  document.querySelectorAll("#meeting-archive-list .delete-meeting").forEach((button) => {
    button.addEventListener("click", () => deleteMeeting(button.dataset.id));
  });
}

function loadMeeting(id) {
  const meeting = state.meetings.find((item) => item.id === id);
  if (!meeting) return;
  $("#meeting-id").value = meeting.id;
  $("#event-title").value = meeting.title;
  $("#event-date").value = meeting.date;
  $("#event-time").value = meeting.start_time;
  $("#event-duration").value = meeting.duration_minutes;
  $("#event-timezone").value = meeting.timezone;
  $("#event-location").value = meeting.location || "";
  $("#event-purpose").value = meeting.purpose || "";
  $("#save-content-local").checked = Boolean(meeting.transcript);
  if (meeting.transcript) {
    $("#transcript").value = meeting.transcript;
    updateCount();
    detectSpeakers();
  }
  if (meeting.analysis) renderResults(meeting.analysis);
}

async function saveCurrentMeeting(includeContent, status = "후보") {
  const schedule = getSchedule();
  const existingId = $("#meeting-id").value;
  const record = {
    id: existingId || crypto.randomUUID(),
    ...schedule,
    status,
    example: false,
    source_label: "Meeting Mirror 분석",
    transcript: includeContent ? $("#transcript").value : null,
    analysis: includeContent ? state.result : null,
    updated_at: new Date().toISOString(),
  };
  await dbOperation("readwrite", (store) => store.put(record));
  state.meetings = await dbOperation("readonly", (store) => store.getAll());
  state.selectedDate = schedule.date;
  state.calendarMonth = new Date(`${schedule.date}T00:00:00`);
  $("#meeting-id").value = record.id;
  renderCalendar();
  return record;
}

async function saveMeeting(event) {
  event.preventDefault();
  try {
    await saveCurrentMeeting($("#save-content-local").checked);
  } catch (error) {
    showError(error.message);
  }
}

async function toggleMeetingStatus(id) {
  const meeting = state.meetings.find((item) => item.id === id);
  if (!meeting) return;
  meeting.status = meeting.status === "확정" ? "후보" : "확정";
  await dbOperation("readwrite", (store) => store.put(meeting));
  state.meetings = await dbOperation("readonly", (store) => store.getAll());
  renderCalendar();
}

async function deleteMeeting(id) {
  await dbOperation("readwrite", (store) => store.delete(id));
  state.meetings = await dbOperation("readonly", (store) => store.getAll());
  renderCalendar();
}

function clearMeetingForm() {
  $("#meeting-id").value = "";
  $("#event-title").value = "";
  $("#event-date").value = state.selectedDate;
  $("#event-time").value = "";
  $("#event-duration").value = "60";
  $("#event-location").value = "";
  $("#event-purpose").value = "";
  $("#save-content-local").checked = false;
}

function insightHtml(insight, className) {
  return `<article class="result-card ${className}">
    <h4>${escapeHtml(insight.title)}</h4>
    <p>${escapeHtml(insight.observation)}</p>
    ${insight.evidence.map(citationHtml).join("")}
    <p class="behavior">다음 행동 → ${escapeHtml(insight.next_behavior)}</p>
  </article>`;
}

function presentationFindingHtml(item, className) {
  return `<article class="result-card ${className}">
    <span class="block-label">${escapeHtml(item.dimension)}</span>
    <h4>${escapeHtml(item.title)}</h4>
    <p>${escapeHtml(item.observation)}</p>
    ${item.evidence.map(citationHtml).join("")}
    <p class="rewrite"><strong>이렇게 바꿔 말하기</strong><br>${escapeHtml(item.rewritten_phrase)}</p>
    <p class="behavior">리허설 → ${escapeHtml(item.rehearsal_action)}</p>
  </article>`;
}

function renderPresentationResults(result) {
  const coaching = result.presentation_coaching;
  $("#results-content").innerHTML = `
    ${executiveHtml(result.executive_summary, result.mode_label, [
      { value: coaching.strengths.length, label: "강점" },
      { value: coaching.improvements.length, label: "개선점" },
      { value: coaching.next_presentation_checklist.length, label: "체크리스트" },
    ])}${agentProofHtml(result)}
    <section class="result-section">
      <h3>발표 코칭 · ${escapeHtml(coaching.speaker)}</h3>
      <p class="summary">${escapeHtml(coaching.overview)}</p>
      <h4>강점</h4>
      <div class="card-grid">${coaching.strengths.map((item) => presentationFindingHtml(item, "strength")).join("")}</div>
      <h4>우선 개선점과 청중 Q&amp;A</h4>
      <div class="card-grid">${coaching.improvements.map((item) => presentationFindingHtml(item, "accent")).join("")}</div>
      <div class="result-card"><h4>다음 발표 체크리스트</h4>${listHtml(coaching.next_presentation_checklist)}</div>
    </section>`;
}

function renderMeetingResults(result) {
  const self = result.self_coaching;
  const stakeholders = result.stakeholders.map((profile) => {
    const hypotheses = profile.hypotheses.map((hypothesis) => `
      <div class="hypothesis">
        <span class="block-label">목적 가설 · 사실 아님</span>
        <p>${escapeHtml(hypothesis.possible_goal_or_concern)}</p>
        <p><strong>확신도</strong> <span class="confidence">${escapeHtml(displayLabel(hypothesis.confidence))} · 텍스트 근거 기준</span></p>
        <div><strong>근거 발언</strong>${hypothesis.citations.map(citationHtml).join("")}</div>
        <p class="behavior"><strong>확인 질문</strong> → ${escapeHtml(hypothesis.confirmation_question)}</p>
      </div>`).join("");
    return `<article class="stakeholder">
      <div class="stakeholder-header"><span class="avatar">${escapeHtml(profile.speaker)}</span>
        <h4>발언자 ${escapeHtml(profile.speaker)}의 관점</h4></div>
      <p class="core-perspective"><strong>핵심 관점 · 가설</strong><br>${escapeHtml(profile.core_perspective)}</p>
      <div class="split">
        <div class="stakeholder-block"><span class="block-label">명시적 요청 · 사실</span>${listHtml(profile.explicit_requests)}</div>
        <div class="stakeholder-block"><span class="block-label">주요 우려 · 사실</span>${listHtml(profile.concerns)}</div>
      </div>${hypotheses}
    </article>`;
  }).join("");
  const plan = result.action_plan;
  const actionRows = plan.action_items.map((item) => `
    <tr><td>${escapeHtml(item.owner)}</td><td>${escapeHtml(item.deadline)}</td>
    <td>${escapeHtml(item.action)}${item.evidence.map(citationHtml).join("")}</td>
    <td>${escapeHtml(displayLabel(item.status))}</td></tr>`).join("");
  $("#results-content").innerHTML = `
    ${executiveHtml(result.executive_summary, result.mode_label, [
      { value: result.stakeholders.length, label: "참여자" },
      { value: plan.decisions.length, label: "결정" },
      { value: plan.action_items.length, label: "실행 항목" },
      { value: plan.unresolved_questions.length, label: "미해결" },
    ])}${agentProofHtml(result)}
    <section class="result-section"><h3>나의 대화 코칭 · ${escapeHtml(self.speaker)}</h3>
      <p class="summary">${escapeHtml(self.summary)}</p>
      <div class="card-grid">
        ${self.strengths.map((item) => insightHtml(item, "strength")).join("")}
        ${self.improvements.map((item) => insightHtml(item, "accent")).join("")}
      </div>
    </section>
    <section class="result-section"><h3>이해관계자 맵</h3>${stakeholders}</section>
    <section class="result-section"><h3>실행 계획</h3>
      <div class="split">
        <div class="result-card"><h4>결정</h4>${listHtml(plan.decisions)}</div>
        <div class="result-card"><h4>미해결 질문</h4>${listHtml(plan.unresolved_questions)}</div>
      </div>
      <h4>담당자 · 기한 · 행동</h4>
      <div style="overflow-x:auto"><table class="action-table">
        <thead><tr><th>담당</th><th>기한</th><th>행동과 근거</th><th>상태</th></tr></thead>
        <tbody>${actionRows}</tbody>
      </table></div>
      <div class="result-card"><h4>추천 후속 조치</h4>${listHtml(plan.recommended_followups)}</div>
    </section>`;
}

function renderResults(result) {
  state.result = result;
  $("#mode-badge").textContent = result.mode_label;
  $("#disclaimer").textContent = `⚠ ${result.disclaimer}`;
  if (result.product_mode === "presentation-coach") renderPresentationResults(result);
  else renderMeetingResults(result);
  if (result.schedule) {
    $("#results-content").insertAdjacentHTML("beforeend", `
      <aside class="calendar-candidate">
        <div><span class="status-chip">캘린더 후보</span>
          <strong>${escapeHtml(result.schedule.title)}</strong>
          <p>${escapeHtml(result.schedule.date)} ${escapeHtml(result.schedule.start_time)} · ${escapeHtml(result.schedule.location || "장소 미정")}</p>
        </div>
        <button id="add-calendar-candidate" class="primary-button" type="button">내 캘린더에 추가</button>
      </aside>`);
    $("#add-calendar-candidate").addEventListener("click", async (event) => {
      try {
        await saveCurrentMeeting(false, "후보");
        event.target.textContent = "추가됨";
        event.target.disabled = true;
      } catch (error) {
        showError(error.message);
      }
    });
  }
  $("#download-calendar").hidden = !result.schedule;
  $("#history-opt-in").hidden = false;
  $("#results").hidden = false;
  $("#results").scrollIntoView({ behavior: "smooth", block: "start" });
}

function showError(message) {
  $("#error-box").textContent = message;
  $("#error-box").hidden = false;
}

function clearResults() {
  state.result = null;
  $("#results").hidden = true;
  $("#pipeline-section").hidden = true;
  $("#error-box").hidden = true;
  $("#history-opt-in").hidden = true;
  resetPipeline();
}

async function analyze() {
  $("#error-box").hidden = true;
  if (!$("#transcript").value.trim()) return showError("대화록을 붙여넣거나 파일/예시를 불러오세요.");
  if (!$("#consent").checked) return showError("분석 권한과 참여자 동의를 확인해 주세요.");
  if (!state.selectedSpeaker) return showError("본인 화자를 선택해 주세요.");
  const button = $("#analyze");
  state.analysisController = new AbortController();
  button.disabled = true;
  $("#cancel-analysis").hidden = false;
  button.firstChild.textContent = "분석 중 ";
  $("#pipeline-section").hidden = false;
  $("#results").hidden = true;
  resetPipeline();
  $("#pipeline-section").scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const payload = {
      transcript: $("#transcript").value,
      self_speaker: state.selectedSpeaker,
      product_mode: state.productMode,
      schedule: getSchedule(),
      mode: "live",
      consent_confirmed: true,
    };
    const parseResponse = await fetch("/api/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: state.analysisController.signal,
    });
    const parseResult = await parseResponse.json();
    if (!parseResponse.ok) {
      throw new Error(parseResult.detail || "대화록 형식을 자동 정리하지 못했습니다.");
    }
    renderSpeakers(parseResult.speakers, state.selectedSpeaker);
    $("#normalization-notice").hidden = parseResult.normalized_lines === 0;
    if (parseResult.normalized_lines) {
      $("#normalization-notice").textContent =
        `${parseResult.normalized_lines}개 줄을 이전 발화에 이어 붙여 자동 정리했습니다.`;
    }
    const response = await fetch("/api/analyze/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: state.analysisController.signal,
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.detail || "분석 요청에 실패했습니다.");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop();
      for (const chunk of chunks) {
        if (!chunk.startsWith("data: ")) continue;
        const event = JSON.parse(chunk.slice(6));
        if (event.type === "progress") setStage(event.stage, event.status, event.detail);
        if (event.type === "heartbeat") {
          const running = document.querySelector(".agent-step.running small");
          if (running) running.textContent = event.message;
        }
        if (event.type === "result") renderResults(event.data);
        if (event.type === "error") throw new Error(event.message);
      }
    }
  } catch (error) {
    showError(error.name === "AbortError" ? "분석을 취소했습니다. 다시 시작할 수 있습니다." : error.message);
    $("#pipeline-section").hidden = true;
  } finally {
    button.disabled = false;
    $("#cancel-analysis").hidden = true;
    state.analysisController = null;
    button.firstChild.textContent = "전문가 Agent 분석 시작 ";
  }
}

function resultAsText() {
  const result = state.result;
  const lines = [
    "Meeting Mirror 분석 결과",
    result.executive_summary.headline,
    ...result.executive_summary.immediate_actions.map((item) => `- 지금 할 일: ${item}`),
    "",
    result.disclaimer,
  ];
  if (result.product_mode === "presentation-coach") {
    const coaching = result.presentation_coaching;
    lines.push("", `[발표 코칭 · ${coaching.speaker}]`);
    for (const item of [...coaching.strengths, ...coaching.improvements]) {
      lines.push(`- ${item.title}: ${item.observation}`, `  바꿔 말하기: ${item.rewritten_phrase}`);
    }
  } else {
    lines.push("", `[나의 코칭 · ${result.self_coaching.speaker}]`);
    for (const item of [...result.self_coaching.strengths, ...result.self_coaching.improvements]) {
      lines.push(`- ${item.title}: ${item.observation}`, `  다음 행동: ${item.next_behavior}`);
    }
  }
  return lines.join("\n");
}

document.querySelectorAll('input[name="product-mode"]').forEach((input) => {
  input.addEventListener("change", (event) => setProductMode(event.target.value));
});
$("#sample-select").addEventListener("change", (event) => {
  const sample = state.samples.find((item) => item.id === event.target.value);
  $("#sample-description").textContent = sample.description;
});
$("#load-sample").addEventListener("click", () => {
  applySample(state.samples.find((sample) => sample.id === $("#sample-select").value));
});
$("#transcript").addEventListener("input", () => { updateCount(); detectSpeakers(); });
$("#browse-files").addEventListener("click", () => $("#file-input").click());
$("#file-input").addEventListener("change", (event) => addFiles(event.target.files));
$("#extract-files").addEventListener("click", extractFiles);
$("#clear-files").addEventListener("click", () => { state.files = []; renderFileQueue(); });
$("#meeting-form").addEventListener("submit", saveMeeting);
$("#new-meeting").addEventListener("click", clearMeetingForm);
$("#prev-month").addEventListener("click", () => {
  state.calendarMonth.setMonth(state.calendarMonth.getMonth() - 1);
  renderCalendar();
});
$("#next-month").addEventListener("click", () => {
  state.calendarMonth.setMonth(state.calendarMonth.getMonth() + 1);
  renderCalendar();
});
$("#clear-meetings").addEventListener("click", async () => {
  if (!window.confirm("이 브라우저에 저장된 모든 일정과 예시를 지울까요?")) return;
  await dbOperation("readwrite", (store) => store.clear());
  state.meetings = [];
  renderCalendar();
});
$("#save-analysis-local").addEventListener("click", async () => {
  try {
    if (!$("#event-title").value.trim()) {
      const now = new Date();
      $("#event-title").value = state.productMode === "presentation-coach"
        ? "발표 코칭 기록"
        : "회의 분석 기록";
      $("#event-date").value = dateKey(now);
      $("#event-time").value = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    }
    $("#save-content-local").checked = true;
    await saveCurrentMeeting(true, "확정");
    $("#history-opt-in").hidden = true;
  } catch (error) {
    showError(error.message);
  }
});
$("#skip-analysis-save").addEventListener("click", () => {
  $("#history-opt-in").hidden = true;
});
const dropZone = $("#drop-zone");
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault(); dropZone.classList.add("dragging");
}));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault(); dropZone.classList.remove("dragging");
}));
dropZone.addEventListener("drop", (event) => addFiles(event.dataTransfer.files));
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") $("#file-input").click();
});
$("#analyze").addEventListener("click", analyze);
$("#cancel-analysis").addEventListener("click", () => state.analysisController?.abort());
$("#reset").addEventListener("click", () => {
  $("#transcript").value = "";
  $("#consent").checked = false;
  state.files = [];
  renderFileQueue();
  updateCount();
  renderSpeakers([]);
  clearMeetingForm();
  clearResults();
});
$("#copy-result").addEventListener("click", async () => {
  await navigator.clipboard.writeText(resultAsText());
  $("#copy-result").textContent = "복사됨";
  setTimeout(() => { $("#copy-result").textContent = "결과 복사"; }, 1500);
});
$("#download-result").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(state.result, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `meeting-mirror-${state.result.analysis_id}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});
$("#download-calendar").addEventListener("click", async () => {
  try {
    const response = await fetch("/api/calendar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(getSchedule()),
    });
    const body = await response.blob();
    if (!response.ok) throw new Error("캘린더 파일을 만들지 못했습니다.");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(body);
    link.download = "meeting-mirror.ics";
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (error) {
    showError(error.message);
  }
});

initialize().catch((error) => showError(error.message));
