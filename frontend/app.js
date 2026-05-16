// ===== App entrypoint: local dashboard vs public read-only dashboard =====

function bindInternalDashboardNav() {
  const nav = document.querySelector(".header-nav");
  if (!nav || nav.dataset.navBound === "1") return;
  nav.dataset.navBound = "1";
  nav.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-view]");
    if (!btn) return;
    const view = btn.dataset.view;
    if (view) switchView(view);
  });
}

async function startInternalDashboard() {
  bindInternalDashboardNav();
  try {
    if (typeof loadShopConfigs === "function") {
      await loadShopConfigs();
    }
    if (typeof loadTasks === "function") {
      await loadTasks();
    }
    if (typeof buildSetupSummary === "function") {
      buildSetupSummary();
    }
    if (typeof renderSetupWorkbench === "function") {
      renderSetupWorkbench();
    }
    if (typeof refreshEdgeSessions === "function") {
      await refreshEdgeSessions();
    }
    if (typeof startSharedPublicDashboard === "function") {
      await startSharedPublicDashboard({ publicMode: false, preserveLocalSnapshot: true });
    }
    setWsStatus("Local admin connected");
  } catch (error) {
    console.error("Internal dashboard initialization failed", error);
    setWsStatus("Local dashboard failed", "bad");
  }
  syncSchedulerButton();
  connectLiveWebSocket({ renderDashboardOnMessage: false });
}

function shouldStartInternalDashboard() {
  return window.location.pathname !== "/dashboard" && Boolean($("dashboard"));
}

if (window.location.pathname === "/dashboard") {
  window.addEventListener("load", () => {
    startSharedPublicDashboard({ publicMode: true });
  });
} else if (shouldStartInternalDashboard()) {
  window.addEventListener("load", () => {
    startInternalDashboard();
  });
}
