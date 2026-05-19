// ===== App entrypoint: local dashboard vs public read-only dashboard =====

// #region agent log
fetch('http://127.0.0.1:7322/ingest/74902c04-2c86-447b-b11e-113b7ea87782',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'4e09f7'},body:JSON.stringify({sessionId:'4e09f7',runId:'pre-fix-rerun',hypothesisId:'H5',location:'frontend/app.js:top-level',message:'app.js loaded with debug instrumentation',data:{path:window.location.pathname,readyState:document.readyState,coreHasSetWsStatus:typeof setWsStatus==='function'},timestamp:Date.now()})}).catch(()=>{});
// #endregion

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
  if (typeof setupDebugPanel === "function") {
    setupDebugPanel();
  }
  try {
    if (typeof loadShopConfigs === "function") {
      await loadShopConfigs();
    }
    if (typeof loadRuntimeSettings === "function") {
      await loadRuntimeSettings();
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
