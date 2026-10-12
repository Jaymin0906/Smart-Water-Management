/**
 * AquaPulse - Animated Tank & Dashboard Telemetry Controller
 * Stage 1: Wave rendering, threshold coloration, and bubble dynamics
 */

function setupWaterTank() {
  const fillElement = document.getElementById("waterFill");
  if (!fillElement) return;

  const currentLevel = parseFloat(fillElement.getAttribute("data-level") || "80");
  const overflowThreshold = parseFloat(fillElement.getAttribute("data-overflow") || "95");
  const lowThreshold = parseFloat(fillElement.getAttribute("data-low") || "20");

  // Determine wave SVG fill color based on configured thresholds
  let waveColor = "#38bdf8"; // Standard cyan-blue
  if (currentLevel >= overflowThreshold) {
    waveColor = "#f87171"; // Overflow crimson alert
    fillElement.classList.add("danger-fill");
    fillElement.classList.remove("warning-fill");
  } else if (currentLevel <= lowThreshold) {
    waveColor = "#fbbf24"; // Low water amber alert
    fillElement.classList.add("warning-fill");
    fillElement.classList.remove("danger-fill");
  } else {
    fillElement.classList.remove("danger-fill");
    fillElement.classList.remove("warning-fill");
  }

  // Generate SVG wave elements for smooth oscillation
  const waveSvgUri = `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 120" preserveAspectRatio="none"><path d="M0,0 C150,90 350,-40 500,50 C650,140 900,-30 1200,40 L1200,120 L0,120 Z" fill="${encodeURIComponent(waveColor)}"/></svg>')`;

  const wave1 = fillElement.querySelector(".wave1");
  const wave2 = fillElement.querySelector(".wave2");

  if (wave1) wave1.style.backgroundImage = waveSvgUri;
  if (wave2) wave2.style.backgroundImage = waveSvgUri;

  // Set visual height safely bounded between 5% and 97% for crisp aesthetics
  const visualHeight = Math.max(5, Math.min(97, currentLevel));
  fillElement.style.height = `${visualHeight}%`;

  // Audio Buzzer for Overflow or Low Alert using Web Audio API
  if (currentLevel >= overflowThreshold) {
    playBuzzerAlarm(880, 440, 3); // High alternating tone for critical overflow
  } else if (currentLevel <= lowThreshold) {
    playBuzzerAlarm(520, 390, 2); // Pulsed tone for low warning
  }
}

// Global audio context for simulated hardware buzzer
let audioCtx = null;
let alarmInterval = null;

function playBuzzerAlarm(freqHigh, freqLow, beeps) {
  // Only start audio if user has interacted or clicks to acknowledge
  const muteBtn = document.getElementById("muteAlarmBtn");
  if (muteBtn) {
    muteBtn.addEventListener("click", () => {
      stopBuzzerAlarm();
      const banner = document.getElementById("overflowAlarmBanner") || document.getElementById("lowAlarmBanner");
      if (banner) {
        banner.style.opacity = "0.7";
      }
      muteBtn.innerText = "🔇 Muted";
      muteBtn.disabled = true;
    });
  }

  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;

    if (!audioCtx) {
      audioCtx = new AudioContext();
    }

    if (audioCtx.state === "suspended") {
      // Browsers require a user click before playing audio
      const resumeAudio = () => {
        if (audioCtx && audioCtx.state === "suspended") {
          audioCtx.resume();
        }
        document.removeEventListener("click", resumeAudio);
      };
      document.addEventListener("click", resumeAudio, { once: true });
    }

    let beepCount = 0;
    alarmInterval = setInterval(() => {
      if (beepCount >= beeps * 2) {
        clearInterval(alarmInterval);
        return;
      }
      try {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "square";
        osc.frequency.value = beepCount % 2 === 0 ? freqHigh : freqLow;
        gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.18);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.2);
      } catch (err) {
        // audio playback blocked or restricted
      }
      beepCount++;
    }, 240);
  } catch (e) {
    // Web audio not supported
  }
}

function stopBuzzerAlarm() {
  if (alarmInterval) {
    clearInterval(alarmInterval);
    alarmInterval = null;
  }
}

// Quick Preset Clicker
function setAndSubmitLevel(targetLevel) {
  const slider = document.getElementById("quickLevelSlider");
  const form = document.getElementById("quickLevelForm");
  if (slider && form) {
    slider.value = targetLevel;
    document.getElementById("quickLevelVal").innerText = targetLevel + "%";
    form.submit();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setupWaterTank();
});
