/**
 * AquaPulse - Main Application Script
 * Stage 1: Responsive drawer, backdrop, alert dismissal & demo helpers
 */

document.addEventListener("DOMContentLoaded", () => {
  // Mobile Sidebar & Backdrop Toggle
  const mobileToggle = document.getElementById("mobileToggle");
  const sidebar = document.getElementById("sidebar");
  const sidebarBackdrop = document.getElementById("sidebarBackdrop");

  function openSidebar() {
    if (sidebar) sidebar.classList.add("open");
    if (sidebarBackdrop) sidebarBackdrop.classList.add("show");
  }

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("open");
    if (sidebarBackdrop) sidebarBackdrop.classList.remove("show");
  }

  if (mobileToggle) {
    mobileToggle.addEventListener("click", () => {
      if (sidebar && sidebar.classList.contains("open")) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener("click", closeSidebar);
  }

  // Close sidebar on ESC key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeSidebar();
    }
  });

  // Dismiss Flash Toast Alerts
  const alertCloses = document.querySelectorAll(".alert-close");
  alertCloses.forEach((btn) => {
    btn.addEventListener("click", () => {
      const alert = btn.closest(".alert");
      if (alert) {
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-8px)";
        setTimeout(() => alert.remove(), 250);
      }
    });
  });

  // Auto-hide success notifications after 5 seconds
  const autoAlerts = document.querySelectorAll(".alert-success");
  autoAlerts.forEach((alert) => {
    setTimeout(() => {
      if (document.body.contains(alert)) {
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-8px)";
        setTimeout(() => alert.remove(), 250);
      }
    }, 5000);
  });

  // 1-Click Demo Login Auto-fill Helper
  const autofillBtn = document.getElementById("autofillDemoBtn");
  if (autofillBtn) {
    autofillBtn.addEventListener("click", () => {
      const userInput = document.getElementById("username");
      const passInput = document.getElementById("password");
      if (userInput && passInput) {
        userInput.value = "admin";
        passInput.value = "water123";
        userInput.focus();
      }
    });
  }
});
