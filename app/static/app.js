const state = { samples: [], selectedSpeaker: "", result: null };
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");

async function loadSamples() {
  const response = await fetch("/api/samples");
  if (!response.ok) throw new Error("샘플을 불러오지 못했습니다.");
  state.samples = await response.json();
  $("#sample-select").innerHTML = state.samples
    .map((sample) => `<option value="${escapeHtml(sample.id)}">${escapeHtml(sample.title)}</option>`)
    .join("");
  applySample(state.samples[0]);
}

async function loadRuntime() {
  const response = await fetch("/api/runtime");
  if (!response.ok) throw new Error("런타임 상태를 확인하지 못했습니다.");
  const runtime = await response.json();
  $("#runtime-status").textContent = runtime.live_available
    ? "Live Agent Framework 경로가 준비되었습니다."
    : "현재는 로그인 없는 demo 경로가 기본입니다.";
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
  state.selectedSpeaker = selected;
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
  if (speakers.length) renderSpeakers(speakers, speakers.includes(state.selectedSpeaker) ? state.selectedSpeaker : speakers[0]);
}

function updateCount() {
  $("#character-count").textContent = `${$("#transcript").value.length.toLocaleString()} / 50,000`;
}

function setStage(stage, status, detail) {
  const element = document.querySelector(`[data-stage="${stage}"]`);
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
  return `<blockquote class="evidence">${time}<strong>${escapeHtml(item.speaker)}</strong> · “${escapeHtml(item.quote)}”</blockquote>`;
}

function insightHtml(insight, className) {
  return `<article class="result-card ${className}">
    <h4>${escapeHtml(insight.title)}</h4>
    <p>${escapeHtml(insight.observation)}</p>
    ${insight.evidence.map(citationHtml).join("")}
    <p class="behavior">다음 행동 → ${escapeHtml(insight.next_behavior)}</p>
  </article>`;
}

function listHtml(items) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderResults(result) {
  state.result = result;
  $("#mode-badge").textContent = result.mode_label;
  $("#disclaimer").textContent = `⚠ ${result.disclaimer}`;
  const self = result.self_coaching;
  const stakeholders = result.stakeholders.map((profile) => {
    const hypotheses = profile.hypotheses.map((hypothesis) => `
      <div class="hypothesis">
        <p><strong>가능한 목표/우려</strong> <span class="confidence">신뢰도 ${escapeHtml(hypothesis.confidence)}</span></p>
        <p>${escapeHtml(hypothesis.possible_goal_or_concern)}</p>
        ${hypothesis.citations.map(citationHtml).join("")}
        <p class="behavior">확인 질문 → ${escapeHtml(hypothesis.confirmation_question)}</p>
      </div>`).join("");
    return `<article class="stakeholder">
      <div class="stakeholder-header"><span class="avatar">${escapeHtml(profile.speaker)}</span><h4>${escapeHtml(profile.speaker)}의 관점</h4></div>
      <div class="split">
        <div><strong>명시적 요청</strong>${listHtml(profile.explicit_requests)}</div>
        <div><strong>명시적 우려</strong>${listHtml(profile.concerns)}</div>
      </div>
      ${hypotheses}
    </article>`;
  }).join("");

  const plan = result.action_plan;
  const actionRows = plan.action_items.map((item) => `
    <tr><td>${escapeHtml(item.owner)}</td><td>${escapeHtml(item.deadline)}</td>
    <td>${escapeHtml(item.action)}${item.evidence.map(citationHtml).join("")}</td>
    <td>${escapeHtml(item.status)}</td></tr>`).join("");

  $("#results-content").innerHTML = `
    <section class="result-section">
      <h3>나의 대화 코칭 · ${escapeHtml(self.speaker)}</h3>
      <p class="summary">${escapeHtml(self.summary)}</p>
      <div class="card-grid">
        ${self.strengths.map((item) => insightHtml(item, "strength")).join("")}
        ${self.improvements.map((item) => insightHtml(item, "accent")).join("")}
      </div>
    </section>
    <section class="result-section">
      <h3>이해관계자 맵</h3>${stakeholders}
    </section>
    <section class="result-section">
      <h3>실행 계획</h3>
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
  resetPipeline();
}

async function analyze() {
  $("#error-box").hidden = true;
  if (!$("#consent").checked) return showError("분석 권한과 참여자 동의를 확인해 주세요.");
  if (!state.selectedSpeaker) return showError("본인 화자를 선택해 주세요.");
  const button = $("#analyze");
  button.disabled = true;
  button.firstChild.textContent = "분석 중 ";
  $("#pipeline-section").hidden = false;
  $("#results").hidden = true;
  resetPipeline();
  $("#pipeline-section").scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const response = await fetch("/api/analyze/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transcript: $("#transcript").value,
        self_speaker: state.selectedSpeaker,
        mode: $("#analysis-mode").value,
        consent_confirmed: true,
      }),
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
        if (event.type === "result") renderResults(event.data);
        if (event.type === "error") throw new Error(event.message);
      }
    }
  } catch (error) {
    showError(error.message);
    $("#pipeline-section").hidden = true;
  } finally {
    button.disabled = false;
    button.firstChild.textContent = "3-Agent 분석 시작 ";
  }
}

function resultAsText() {
  const result = state.result;
  const lines = ["Meeting Mirror 분석 결과", result.disclaimer, "", `[나의 코칭 · ${result.self_coaching.speaker}]`];
  for (const item of [...result.self_coaching.strengths, ...result.self_coaching.improvements]) {
    lines.push(`- ${item.title}: ${item.observation}`, `  다음 행동: ${item.next_behavior}`);
  }
  lines.push("", "[이해관계자]");
  for (const person of result.stakeholders) {
    lines.push(`- ${person.speaker}: ${person.hypotheses[0].possible_goal_or_concern}`, `  확인: ${person.hypotheses[0].confirmation_question}`);
  }
  lines.push("", "[실행 항목]");
  for (const item of result.action_plan.action_items) lines.push(`- ${item.owner} / ${item.deadline}: ${item.action}`);
  return lines.join("\n");
}

$("#sample-select").addEventListener("change", (event) => {
  applySample(state.samples.find((sample) => sample.id === event.target.value));
});
$("#load-sample").addEventListener("click", () => applySample(state.samples.find((sample) => sample.id === $("#sample-select").value)));
$("#transcript").addEventListener("input", () => { updateCount(); detectSpeakers(); });
$("#analyze").addEventListener("click", analyze);
$("#reset").addEventListener("click", () => {
  $("#transcript").value = "";
  $("#consent").checked = false;
  updateCount();
  renderSpeakers([]);
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

Promise.all([loadSamples(), loadRuntime()]).catch((error) => showError(error.message));
