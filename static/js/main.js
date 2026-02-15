// Frontend logic for Smart Automated Closet kiosk UI.
//
// This file uses the Fetch API to talk to the Flask backend.
// It is intentionally dependency-free (no frameworks) so that it
// runs comfortably on a Raspberry Pi.

const statusEl = document.getElementById("system-status");
const messageArea = document.getElementById("message-area");
const itemsListEl = document.getElementById("items-list");
const recommendationViewEl = document.getElementById("recommendation-view");

const scanBtn = document.getElementById("scan-btn");
const recommendBtn = document.getElementById("recommend-btn");
const yesBtn = document.getElementById("yes-btn");
const noBtn = document.getElementById("no-btn");

const manualTopTypeEl = document.getElementById("manual-top-type");
const manualBottomTypeEl = document.getElementById("manual-bottom-type");

let lastRecommendation = null;

function setStatus(text, colorClass = "ok") {
  statusEl.textContent = text;
  statusEl.style.backgroundColor =
    colorClass === "error" ? "#c62828" : "#2e7d32";
}

function setMessage(text) {
  messageArea.textContent = text;
}

function renderItems(items) {
  itemsListEl.innerHTML = "";
  if (!items || items.length === 0) {
    itemsListEl.innerHTML =
      '<p class="placeholder">No items scanned yet. Run "Scan Carousel".</p>';
    return;
  }
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "item-row";
    const slotSpan = document.createElement("span");
    slotSpan.className = "item-slot";
    slotSpan.textContent = `Slot ${item.slot}`;

    const typeSpan = document.createElement("span");
    typeSpan.className = "item-type";
    typeSpan.textContent = item.type;

    row.appendChild(slotSpan);
    row.appendChild(typeSpan);
    itemsListEl.appendChild(row);
  }
}

function renderRecommendation(reco) {
  if (!reco) {
    recommendationViewEl.innerHTML =
      '<p class="placeholder">No recommendation available.</p>';
    return;
  }

  recommendationViewEl.innerHTML = "";
  const card = document.createElement("div");
  card.className = "outfit-card";

  const topRow = document.createElement("div");
  topRow.className = "outfit-item";
  topRow.innerHTML = `<span>Top</span><span>Slot ${reco.top.slot} • ${reco.top.type}</span>`;

  const bottomRow = document.createElement("div");
  bottomRow.className = "outfit-item";
  bottomRow.innerHTML = `<span>Bottom</span><span>Slot ${reco.bottom.slot} • ${reco.bottom.type}</span>`;

  card.appendChild(topRow);
  card.appendChild(bottomRow);
  recommendationViewEl.appendChild(card);
}

async function apiGetItems() {
  const res = await fetch("/api/items");
  return res.json();
}

// Flowchart (frontend, textual):
// ------------------------------
// [Scan button tapped]
//   -> call /api/scan
//   -> update status + items list
// [Recommend button tapped]
//   -> gather form inputs
//   -> call /api/recommend
//   -> show outfit
// [YES button tapped]
//   -> apply manual corrections (if any)
//   -> call /api/confirm with accepted=true
//   -> backend rotates carousel
// [NO button tapped]
//   -> call /api/confirm with accepted=false
//   -> allow user to request new recommendation

scanBtn.addEventListener("click", async () => {
  try {
    setStatus("Scanning...", "ok");
    setMessage("Capturing image and detecting clothes...");
    const res = await fetch("/api/scan", { method: "POST" });
    const data = await res.json();
    if (data.status === "ok") {
      renderItems(data.items);
      setStatus("Scan complete", "ok");
      setMessage("Scan complete. You can now request a recommendation.");
    } else {
      setStatus("Scan error", "error");
      setMessage(data.message || "Scan failed.");
    }
  } catch (err) {
    console.error(err);
    setStatus("Scan error", "error");
    setMessage("Unexpected error during scan.");
  }
});

recommendBtn.addEventListener("click", async () => {
  try {
    const mood = document.getElementById("mood").value;
    const occasion = document.getElementById("occasion").value;
    const weather = document.getElementById("weather").value;
    const timeOfDay = document.getElementById("timeOfDay").value;

    setStatus("Recommending...", "ok");
    setMessage("Computing best outfit for your preferences...");

    const res = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mood, occasion, weather, timeOfDay }),
    });
    const data = await res.json();
    if (data.status === "ok") {
      lastRecommendation = data.recommendation;
      renderRecommendation(lastRecommendation);
      setStatus("Recommendation ready", "ok");
      setMessage("Review the outfit and press YES to deliver or NO to retry.");
    } else if (data.status === "no_recommendation") {
      lastRecommendation = null;
      renderRecommendation(null);
      setStatus("No outfit", "error");
      setMessage(data.message);
    } else {
      setStatus("Error", "error");
      setMessage(data.message || "Recommendation failed.");
    }
  } catch (err) {
    console.error(err);
    setStatus("Error", "error");
    setMessage("Unexpected error during recommendation.");
  }
});

yesBtn.addEventListener("click", async () => {
  if (!lastRecommendation) {
    setMessage("No recommendation to confirm. Please request one first.");
    return;
  }

  // Manual correction: override detected type if user chose a value.
  const manualTopType = manualTopTypeEl.value;
  const manualBottomType = manualBottomTypeEl.value;

  const payload = {
    accepted: true,
    top: {
      ...lastRecommendation.top,
      ...(manualTopType ? { type: manualTopType } : {}),
    },
    bottom: {
      ...lastRecommendation.bottom,
      ...(manualBottomType ? { type: manualBottomType } : {}),
    },
  };

  try {
    setStatus("Delivering...", "ok");
    setMessage("Rotating carousel to bring clothes to pickup point...");
    const res = await fetch("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.status === "ok") {
      setStatus("Delivered", "ok");
      setMessage("Outfit delivered. Enjoy your day!");
    } else {
      setStatus("Error", "error");
      setMessage(data.message || "Delivery failed.");
    }
  } catch (err) {
    console.error(err);
    setStatus("Error", "error");
    setMessage("Unexpected error during delivery.");
  }
});

noBtn.addEventListener("click", async () => {
  try {
    await fetch("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ accepted: false }),
    });
  } catch (err) {
    console.error(err);
  }
  lastRecommendation = null;
  renderRecommendation(null);
  setStatus("Rejected", "ok");
  setMessage("Okay, please adjust your preferences and try again.");
});

// Initial fetch of items (in case DB already has entries).
(async () => {
  try {
    const data = await apiGetItems();
    if (data.status === "ok") {
      renderItems(data.items);
    }
  } catch {
    // ignore; likely first run
  }
})();

