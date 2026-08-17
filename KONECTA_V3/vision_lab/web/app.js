/**
 * Vision Lab Frontend Application
 */

// State
let currentDataset = null;
let currentVideo = null;
let currentFrameIndex = 0;

const API_BASE = "/api";

// DOM Elements
const discoveryBtn = document.getElementById("btn-discover");
const datasetPathInput = document.getElementById("dataset-path");
const datasetInfo = document.getElementById("dataset-info");
const loadingIndicator = document.getElementById("loading-indicator");
const videoList = document.getElementById("video-list");
const navItems = document.querySelectorAll(".nav-item");
const tabContents = document.querySelectorAll(".tab-content");

// Event Listeners
discoveryBtn.addEventListener("click", discoverDataset);
navItems.forEach((item) => {
    item.addEventListener("click", (e) => switchTab(e.target.dataset.tab));
});

// Tab switching
function switchTab(tabName) {
    navItems.forEach((item) => {
        item.classList.toggle("active", item.dataset.tab === tabName);
    });
    tabContents.forEach((tab) => {
        tab.classList.toggle("active", tab.id === tabName);
    });
}

// Dataset Discovery
async function discoverDataset() {
    const path = datasetPathInput.value.trim();
    if (!path) {
        alert("Please enter a dataset path");
        return;
    }

    loadingIndicator.classList.remove("hidden");
    datasetInfo.classList.add("hidden");
    videoList.innerHTML = "";

    try {
        const response = await fetch(`${API_BASE}/datasets/discover`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path }),
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        currentDataset = await response.json();
        displayDatasetInfo();
        loadVideoList();
    } catch (error) {
        console.error("Discovery failed:", error);
        alert("Discovery failed: " + error.message);
    } finally {
        loadingIndicator.classList.add("hidden");
    }
}

async function displayDatasetInfo() {
    try {
        const response = await fetch(`${API_BASE}/datasets/current`);
        const data = await response.json();

        document.getElementById("stat-videos").textContent = data.videos;
        document.getElementById("stat-classes").textContent = data.classes;
        document.getElementById("stat-signers").textContent = data.signers.length;

        // Display class distribution
        const dist = data.class_distribution;
        const chartHtml = Object.entries(dist)
            .slice(0, 10)
            .map(
                ([cls, count]) =>
                    `<div class="stat-row">
                <span>${cls}</span>
                <div class="bar" style="width: ${Math.min(count * 10, 100)}px; height: 20px; background: var(--primary); border-radius: 3px;"></div>
                <span>${count}</span>
            </div>`
            )
            .join("");

        document.getElementById("class-distribution").innerHTML = chartHtml;
        datasetInfo.classList.remove("hidden");
    } catch (error) {
        console.error("Failed to load dataset info:", error);
    }
}

async function loadVideoList() {
    try {
        const response = await fetch(`${API_BASE}/datasets/current`);
        const data = await response.json();

        // Create video cards (sample - ideally we'd have a dedicated endpoint)
        videoList.innerHTML =
            data.classes && data.classes.length > 0
                ? `<p>Dataset loaded with ${data.classes.length} classes. Select a class below.</p>`
                : `<p>No videos found in dataset.</p>`;
    } catch (error) {
        console.error("Failed to load videos:", error);
    }
}

// Frame navigation
function setupFrameNavigation() {
    const prevBtn = document.getElementById("btn-prev");
    const nextBtn = document.getElementById("btn-next");
    const slider = document.getElementById("frame-slider");

    prevBtn.addEventListener("click", () => {
        currentFrameIndex = Math.max(0, currentFrameIndex - 1);
        updateFrame();
    });

    nextBtn.addEventListener("click", () => {
        currentFrameIndex = Math.min(
            currentVideo.frames - 1,
            currentFrameIndex + 1
        );
        updateFrame();
    });

    slider.addEventListener("change", (e) => {
        currentFrameIndex = parseInt(e.target.value);
        updateFrame();
    });
}

async function updateFrame() {
    if (!currentVideo) return;

    try {
        // Load frame with landmarks
        const withLandmarks = document.getElementById("toggle-landmarks")?.checked || false;
        const response = await fetch(
            `${API_BASE}/videos/${currentVideo.id}/frame/${currentFrameIndex}?with_landmarks=${withLandmarks}`
        );
        const data = await response.json();

        document.getElementById("frame-image").src = data.image;
        document.getElementById("current-frame").textContent = currentFrameIndex;
        document.getElementById("frame-slider").value = currentFrameIndex;

        // Load quality info for this frame
        await loadFrameQuality(currentFrameIndex);
    } catch (error) {
        console.error("Failed to load frame:", error);
    }
}

async function loadFrameQuality(frameId) {
    if (!currentVideo) return;

    try {
        const response = await fetch(`${API_BASE}/videos/${currentVideo.id}/quality`);
        const data = await response.json();

        if (data.frames && frameId < data.frames.length) {
            const frameQuality = data.frames[frameId];
            displayFrameQuality(frameQuality);
        }
    } catch (error) {
        // Quality data not available yet
    }
}

function displayFrameQuality(quality) {
    document.getElementById("frame-quality-score").textContent = quality.score;
    document.getElementById("frame-quality-status").textContent = quality.status;
    document.getElementById("frame-quality-status").className = `quality-status ${quality.status.toLowerCase()}`;

    const issuesHtml = quality.issues.length > 0
        ? `<div class="quality-issues">${quality.issues.map(issue => `<div class="issue">⚠️ ${issue}</div>`).join('')}</div>`
        : '<div class="quality-issues"><div class="issue">✓ No issues detected</div></div>';

    document.getElementById("frame-quality-issues").innerHTML = issuesHtml;
}

async function extractLandmarks() {
    if (!currentVideo) return;

    const btn = document.getElementById("btn-extract-landmarks");
    btn.disabled = true;
    btn.textContent = "Extracting...";

    try {
        const response = await fetch(
            `${API_BASE}/videos/${currentVideo.id}/extract-landmarks`,
            { method: "POST" }
        );

        if (!response.ok) {
            throw new Error(await response.text());
        }

        const result = await response.json();

        document.getElementById("stat-valid-frames").textContent = result.valid_frames;
        document.getElementById("stat-detection-rate").textContent = (result.detection_rate * 100).toFixed(1) + "%";
        document.getElementById("stat-avg-confidence").textContent = (result.avg_confidence * 100).toFixed(1) + "%";

        // Load temporal analysis
        await loadTemporalAnalysis();

        // Load frame 0 quality
        currentFrameIndex = 0;
        await updateFrame();

        alert("Landmark extraction complete!");
    } catch (error) {
        console.error("Extraction failed:", error);
        alert("Extraction failed: " + error.message);
    } finally {
        btn.disabled = false;
        btn.textContent = "Extract Landmarks";
    }
}

async function loadTemporalAnalysis() {
    if (!currentVideo) return;

    try {
        const response = await fetch(`${API_BASE}/videos/${currentVideo.id}/temporal`);
        const data = await response.json();

        const temporal = document.getElementById("stat-temporal");
        if (temporal) {
            temporal.innerHTML = `
                <div class="stat-row">
                    <span>Avg Velocity:</span>
                    <strong>${(data.avg_velocity || 0).toFixed(3)}</strong>
                </div>
                <div class="stat-row">
                    <span>Avg Acceleration:</span>
                    <strong>${(data.avg_acceleration || 0).toFixed(4)}</strong>
                </div>
                <div class="stat-row">
                    <span>Temporal Consistency:</span>
                    <strong>${(data.consistency_score * 100).toFixed(1)}%</strong>
                </div>
                <div class="stat-row">
                    <span>Frames with Gaps:</span>
                    <strong>${data.frames_with_gaps}</strong>
                </div>
            `;
        }
    } catch (error) {
        console.error("Failed to load temporal analysis:", error);
    }
}

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    setupFrameNavigation();

    const extractBtn = document.getElementById("btn-extract-landmarks");
    if (extractBtn) {
        extractBtn.addEventListener("click", extractLandmarks);
    }

    // Toggle landmarks checkbox
    const toggleLandmarks = document.getElementById("toggle-landmarks");
    if (toggleLandmarks) {
        toggleLandmarks.addEventListener("change", updateFrame);
    }

    // Set default path (for convenience during dev)
    datasetPathInput.value = "C:\\KONECTA\\Datasets\\videos UFPE (V-LIBRASIL)";
});
