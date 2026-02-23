const strengthScore = (value) => {
    let score = 0;
    if (value.length >= 8) score += 1;
    if (/[A-Z]/.test(value)) score += 1;
    if (/[a-z]/.test(value)) score += 1;
    if (/\d/.test(value)) score += 1;
    if (/[^\w\s]/.test(value)) score += 1;
    return Math.min(score, 5);
};

const strengthLabel = (score) => {
    if (score <= 1) return "Very Weak";
    if (score === 2) return "Weak";
    if (score === 3) return "Medium";
    if (score === 4) return "Strong";
    return "Very Strong";
};

document.addEventListener("DOMContentLoaded", () => {
    const wrappers = document.querySelectorAll(".password-meter");
    if (!wrappers.length) return;

    wrappers.forEach((meter) => {
        const group = meter.closest(".form-group");
        const passwordInput = group ? group.querySelector('input[name="password"]') : null;
        const bar = meter.querySelector(".password-meter-bar");
        const text = group ? group.querySelector(".password-meter-text") : null;

        if (!passwordInput || !bar || !text) return;

        const updateMeter = () => {
            const value = passwordInput.value || "";
            const score = strengthScore(value);
            meter.setAttribute("data-level", String(score));
            const percent = Math.max(8, score * 20);
            bar.style.width = `${percent}%`;
            if (!value) {
                text.textContent = "Strength: enter password";
            } else {
                text.textContent = `Strength: ${strengthLabel(score)}`;
            }
        };

        passwordInput.addEventListener("input", updateMeter);
        updateMeter();
    });

    document.querySelectorAll(".password-toggle").forEach((btn) => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target");
            const input = document.getElementById(targetId);
            if (!input) return;
            const isHidden = input.type === "password";
            input.type = isHidden ? "text" : "password";
            const icon = btn.querySelector("i");
            if (icon) {
                icon.classList.toggle("fa-eye", !isHidden);
                icon.classList.toggle("fa-eye-slash", isHidden);
            }
        });
    });
});
