(function () {
  window.addEventListener("load", () => {
    document.body.classList.add("test-dashboard-mode");
    startSharedPublicDashboard({ publicMode: true });
  });
})();
