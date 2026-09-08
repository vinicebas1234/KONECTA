// Libras Learning Agent — Ciclo 10: UI da fila de validação.
// Vanilla JS, fetch() puro contra a própria API (mesma origem, sem CORS).
// Sem framework, sem build step — mesmo espírito de vision_lab/web/.

const API = "/api/libras";

const DECISIONS = [
    { value: "approved", label: "Aprovado", cls: "success" },
    { value: "rejected", label: "Rejeitado", cls: "danger" },
    { value: "corrected", label: "Corrigido", cls: "warning" },
    { value: "needs_review", label: "Precisa revisão", cls: "secondary" },
];

function esc(s) {
    const div = document.createElement("div");
    div.textContent = s ?? "";
    return div.innerHTML;
}

function fmtDate(iso) {
    if (!iso) return "-";
    return new Date(iso).toLocaleString("pt-BR");
}

// `Source.url` vem de busca externa (research/web_search.py) -- confiável na
// prática (URLs reais devolvidas pelo DuckDuckGo), mas nunca validado contra
// esquema. `esc()` escapa entidades HTML, não impede um href="javascript:...";
// só deixa clicável quando o esquema é http/https, senão mostra como texto puro.
function safeHref(url) {
    if (!url) return null;
    try {
        const parsed = new URL(url, location.href);
        return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
    } catch (_) {
        return null;
    }
}

// Lê o corpo JSON do erro (a API sempre devolve {"detail": "..."}) para
// mostrar a mensagem de verdade na tela, em vez de um alert genérico.
async function apiFetch(path, opts) {
    const res = await fetch(API + path, opts);
    let body = null;
    try {
        body = await res.json();
    } catch (_) {
        // corpo vazio/não-JSON — segue sem `body`
    }
    if (!res.ok) {
        const detail = (body && body.detail) || `HTTP ${res.status}`;
        const err = new Error(detail);
        err.status = res.status;
        throw err;
    }
    return body;
}

// --------------------------------------------------------------------- stats ---

async function renderStats() {
    const el = document.getElementById("stats");
    try {
        const stats = await apiFetch("/stats");
        const signalBadges = Object.entries(stats.signals_by_status)
            .filter(([, count]) => count > 0)
            .map(([status, count]) => `<span class="badge">${esc(status)}: <strong>${count}</strong></span>`)
            .join("");
        const modelBadges = Object.entries(stats.models_by_status)
            .filter(([, count]) => count > 0)
            .map(([status, count]) => `<span class="badge">modelo ${esc(status)}: <strong>${count}</strong></span>`)
            .join("");
        el.innerHTML =
            `<span class="badge">Sinais total: <strong>${stats.signals_total}</strong></span>` +
            signalBadges +
            `<span class="badge">Modelos total: <strong>${stats.models_total}</strong></span>` +
            modelBadges;
    } catch (err) {
        el.innerHTML = `<span class="badge">Não foi possível carregar estatísticas: ${esc(err.message)}</span>`;
    }
}

// --------------------------------------------------------------------- fila (queue) ---

async function renderQueue() {
    const view = document.getElementById("view");
    view.innerHTML = "<p>Carregando fila…</p>";

    let candidates;
    try {
        candidates = await apiFetch("/candidates?status=VALIDATION_REQUIRED");
    } catch (err) {
        view.innerHTML = `<div class="error-box">Erro ao carregar a fila: ${esc(err.message)}</div>`;
        return;
    }

    if (candidates.length === 0) {
        view.innerHTML = `<h2>Fila de validação</h2><p class="placeholder">Nada para validar agora.</p>`;
        return;
    }

    // ponytail: contagem de fontes não vem em CandidateSummary (GET /candidates) —
    // um fetch de detalhe por item (N+1) resolve sem mexer no schema da API.
    // Se a fila crescer muito, trocar por um campo sources_count agregado no backend.
    const withCounts = await Promise.all(
        candidates.map(async (c) => {
            try {
                const detail = await apiFetch(`/candidates/${c.id}`);
                return { ...c, sourcesCount: detail.sources.length };
            } catch (_) {
                return { ...c, sourcesCount: "?" };
            }
        })
    );

    view.innerHTML =
        `<h2>Fila de validação (${withCounts.length})</h2>` +
        withCounts
            .map(
                (c) => `
        <div class="card queue-item" data-id="${esc(c.id)}">
            <div>
                <div class="concept">${esc(c.concept)}</div>
                <div class="meta">criado em ${fmtDate(c.created_at)} · ${c.sourcesCount} fonte(s)</div>
            </div>
            <button class="secondary">Abrir</button>
        </div>`
            )
            .join("");

    view.querySelectorAll(".queue-item").forEach((el) => {
        el.addEventListener("click", () => {
            location.hash = `#/candidates/${el.dataset.id}`;
        });
    });
}

// --------------------------------------------------------------------- detalhe ---

function renderEventPayload(event) {
    if (event.event_type === "research_completed" && event.payload) {
        const p = event.payload;
        return `
            <div class="event-payload">
                classificação: <strong>${esc(p.classification ?? "-")}</strong>
                (confiança: ${p.confidence != null ? p.confidence : "-"})<br>
                fontes usadas: ${p.sources_count ?? "-"}<br>
                raciocínio: ${esc(p.reasoning ?? "-")}
            </div>`;
    }
    if (!event.payload) return "";
    const entries = Object.entries(event.payload)
        .filter(([k]) => k !== "signal_id")
        .map(([k, v]) => `${esc(k)}: ${esc(typeof v === "object" ? JSON.stringify(v) : v)}`)
        .join(" · ");
    return entries ? `<div class="event-payload">${entries}</div>` : "";
}

async function renderDetail(id) {
    const view = document.getElementById("view");
    view.innerHTML = "<p>Carregando candidato…</p>";

    let candidate;
    try {
        candidate = await apiFetch(`/candidates/${id}`);
    } catch (err) {
        view.innerHTML =
            `<a href="#/" class="back-link">← voltar à fila</a>` +
            `<div class="error-box">Erro ao carregar candidato: ${esc(err.message)}</div>`;
        return;
    }

    const sourcesHtml = candidate.sources.length
        ? candidate.sources
              .map((s) => {
                  const href = safeHref(s.url);
                  const link = href
                      ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(s.url)}</a>`
                      : s.url
                        ? `<span class="meta">${esc(s.url)}</span>`
                        : "";
                  return `
            <div class="source-item">
                <div>${esc(s.title || "(sem título)")}</div>
                ${link}
            </div>`;
              })
              .join("")
        : `<p class="placeholder">Nenhuma fonte vinculada.</p>`;

    const eventsHtml = candidate.events.length
        ? candidate.events
              .map(
                  (e) => `
            <div class="event-item ${esc(e.event_type)}">
                <span class="event-type">${esc(e.event_type)}</span>
                <span class="event-time">${fmtDate(e.timestamp)}</span>
                ${renderEventPayload(e)}
            </div>`
              )
              .join("")
        : `<p class="placeholder">Nenhum evento registrado.</p>`;

    const decisionButtons = DECISIONS.map(
        (d) => `<button type="button" class="${d.cls}" data-decision="${d.value}">${d.label}</button>`
    ).join("");

    view.innerHTML = `
        <a href="#/" class="back-link">← voltar à fila</a>
        <div class="card">
            <h2>${esc(candidate.concept)}</h2>
            <p><strong>Status:</strong> ${esc(candidate.status)}
               ${candidate.category ? ` · <strong>Categoria:</strong> ${esc(candidate.category)}` : ""}</p>
            ${candidate.description ? `<p>${esc(candidate.description)}</p>` : ""}
            <p class="meta">criado em ${fmtDate(candidate.created_at)} · atualizado em ${fmtDate(candidate.updated_at)}</p>
        </div>

        <div class="card">
            <h3>Fontes vinculadas</h3>
            ${sourcesHtml}
        </div>

        <div class="card">
            <h3>Histórico de eventos</h3>
            ${eventsHtml}
        </div>

        <div class="card">
            <h3>Decisão de validação</h3>
            <div class="decision-form">
                <input type="text" id="validator-name" placeholder="Seu nome (validador)" required>
                <textarea id="validator-notes" placeholder="Notas (opcional)" rows="2"></textarea>
                <div class="decision-buttons">${decisionButtons}</div>
            </div>
            <div id="validation-result"></div>
        </div>
    `;

    view.querySelectorAll("[data-decision]").forEach((btn) => {
        btn.addEventListener("click", () => submitValidation(id, btn.dataset.decision));
    });
}

async function submitValidation(id, decision) {
    const resultEl = document.getElementById("validation-result");
    const validator = document.getElementById("validator-name").value.trim();
    const notes = document.getElementById("validator-notes").value.trim();

    if (!validator) {
        resultEl.innerHTML = `<div class="error-box">Informe o nome do validador antes de decidir.</div>`;
        return;
    }

    try {
        await apiFetch(`/candidates/${id}/validation`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ decision, validator, notes: notes || null }),
        });
        await renderStats();
        location.hash = "#/";
    } catch (err) {
        // 409 (transição ilegal) / 400 (decision inválida) / 404: mensagem legível
        // da própria API, não um alert genérico.
        resultEl.innerHTML = `<div class="error-box">Não foi possível registrar a decisão (HTTP ${err.status}): ${esc(err.message)}</div>`;
    }
}

// --------------------------------------------------------------------- modelos (bônus) ---

async function renderModels() {
    const view = document.getElementById("view");
    view.innerHTML = "<p>Carregando modelos…</p>";

    let models;
    try {
        models = await apiFetch("/models");
    } catch (err) {
        view.innerHTML = `<div class="error-box">Erro ao carregar modelos: ${esc(err.message)}</div>`;
        return;
    }

    if (models.length === 0) {
        view.innerHTML = `<h2>Modelos</h2><p class="placeholder">Nenhum modelo treinado ainda.</p>`;
        return;
    }

    view.innerHTML = `
        <h2>Modelos</h2>
        <table>
            <thead>
                <tr><th>Versão</th><th>Status</th><th>Sinais</th><th>Top-1</th><th>Top-5</th><th>Criado em</th></tr>
            </thead>
            <tbody>
                ${models
                    .map(
                        (m) => `
                    <tr>
                        <td>${esc(m.version)}</td>
                        <td>${esc(m.status)}</td>
                        <td>${m.signals_count ?? "-"}</td>
                        <td>${m.top1_accuracy != null ? (m.top1_accuracy * 100).toFixed(1) + "%" : "-"}</td>
                        <td>${m.top5_accuracy != null ? (m.top5_accuracy * 100).toFixed(1) + "%" : "-"}</td>
                        <td>${fmtDate(m.created_at)}</td>
                    </tr>`
                    )
                    .join("")}
            </tbody>
        </table>
    `;
}

// --------------------------------------------------------------------- pesquisa nova ---

document.getElementById("research-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const input = document.getElementById("research-concept");
    const resultEl = document.getElementById("research-result");
    const concept = input.value.trim();
    if (!concept) return;

    const submitBtn = ev.target.querySelector("button");
    submitBtn.disabled = true;
    resultEl.innerHTML = "<p>Pesquisando… (isto pode levar alguns segundos)</p>";

    try {
        const result = await apiFetch("/research", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ concept }),
        });
        resultEl.innerHTML = `<div class="success-box">
            "${esc(result.concept)}" pesquisado — status: <strong>${esc(result.status)}</strong>
            ${result.classification ? ` · classificação: ${esc(result.classification)}` : ""}
        </div>`;
        input.value = "";
        await renderStats();
        if (!location.hash || location.hash === "#/") renderQueue();
    } catch (err) {
        // 502 = cota do Gemini/busca externa esgotada (WebSearchError/SourceComparisonError
        // mapeadas em api/app.py) — mostra o texto real da API, não um alert genérico.
        resultEl.innerHTML = `<div class="error-box">Pesquisa falhou (HTTP ${err.status}): ${esc(err.message)}</div>`;
    } finally {
        submitBtn.disabled = false;
    }
});

// --------------------------------------------------------------------- roteamento ---

function setActiveTab(name) {
    document.querySelectorAll(".tab-link").forEach((a) => {
        a.classList.toggle("active", a.dataset.tab === name);
    });
}

function route() {
    const hash = location.hash || "#/";
    const candidateMatch = hash.match(/^#\/candidates\/(.+)$/);

    if (hash === "#/models") {
        setActiveTab("models");
        renderModels();
    } else if (candidateMatch) {
        setActiveTab("queue");
        renderDetail(decodeURIComponent(candidateMatch[1]));
    } else {
        setActiveTab("queue");
        renderQueue();
    }
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", () => {
    renderStats();
    route();
});
