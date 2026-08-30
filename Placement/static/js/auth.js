/**
 * Auth page interactivity
 * - Login: role tab switching
 * - Register: dynamic field toggling based on selected role
 */

document.addEventListener("DOMContentLoaded", () => {
    // ── Login Page: Role Tabs ──
    const roleTabs = document.getElementById("roleTabs");
    const selectedRoleInput = document.getElementById("selectedRole");
    const roleLabel = document.getElementById("roleLabel");

    if (roleTabs) {
        roleTabs.addEventListener("click", (e) => {
            const tab = e.target.closest(".role-tab");
            if (!tab) return;

            // Update active state
            roleTabs.querySelectorAll(".role-tab").forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");

            // Update hidden input and button label
            const role = tab.dataset.role;
            selectedRoleInput.value = role;
            roleLabel.textContent = capitalize(role);
        });
    }

    // ── Register Page: Dynamic Fields ──
    const roleSelect = document.getElementById("role");

    if (roleSelect) {
        roleSelect.addEventListener("change", () => {
            const selected = roleSelect.value;

            // Hide all role-specific field groups
            document.querySelectorAll(".role-fields").forEach((group) => {
                group.classList.add("hidden");
                // Disable hidden inputs so they don't submit
                group.querySelectorAll("input").forEach((inp) => (inp.disabled = true));
            });

            // Show the selected one
            const target = document.getElementById(`fields-${selected}`);
            if (target) {
                target.classList.remove("hidden");
                target.querySelectorAll("input").forEach((inp) => (inp.disabled = false));
            }
        });

        // Trigger on load to set initial state
        roleSelect.dispatchEvent(new Event("change"));
    }

    // ── Auto-dismiss flash messages ──
    document.querySelectorAll(".flash").forEach((el) => {
        setTimeout(() => {
            el.style.opacity = "0";
            el.style.transform = "translateY(-8px)";
            setTimeout(() => el.remove(), 300);
        }, 5000);
    });
});

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}
