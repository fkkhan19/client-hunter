/* ===========================================
   GLOBAL UTILS
   =========================================== */

// Close modal on Escape
document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") closeModal();
});

/* ===========================================
   MODAL FUNCTIONS
   =========================================== */

function openMessageForm(id, name) {
    document.getElementById("modalLeadId").value = id;
    document.getElementById("modalLeadName").innerText = "Send to " + name;
    document.getElementById("messageModal").style.display = "flex";
}

function closeModal() {
    document.getElementById("messageModal").style.display = "none";
}

/* ===========================================
   LIVE SEARCH FILTER
   =========================================== */

function filterLeads() {
    const input = document.getElementById("searchInput").value.toLowerCase();
    const rows = document.querySelectorAll(".lead-table tbody tr");

    rows.forEach(row => {
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(input) ? "" : "none";
    });
}

/* ===========================================
   PAGINATION
   =========================================== */

let currentPage = 1;
const rowsPerPage = 12;

function paginateTable() {
    const rows = [...document.querySelectorAll(".lead-table tbody tr")];
    const totalRows = rows.length;
    const totalPages = Math.ceil(totalRows / rowsPerPage);

    rows.forEach((row, index) => {
        row.style.display =
            index >= (currentPage - 1) * rowsPerPage &&
            index < currentPage * rowsPerPage
                ? ""
                : "none";
    });

    renderPaginationButtons(totalPages);
}

function changePage(page) {
    currentPage = page;
    paginateTable();
}

function renderPaginationButtons(totalPages) {
    const container = document.getElementById("pagination");
    if (!container) return;

    let html = "";

    if (currentPage > 1) {
        html += `<button onclick="changePage(${currentPage - 1})">Prev</button>`;
    }

    for (let i = 1; i <= totalPages; i++) {
        html += `<button class="${i === currentPage ? 'active-page' : ''}" onclick="changePage(${i})">${i}</button>`;
    }

    if (currentPage < totalPages) {
        html += `<button onclick="changePage(${currentPage + 1})">Next</button>`;
    }

    container.innerHTML = html;
}

/* ===========================================
   MULTI DELETE
   =========================================== */

function toggleSelectAll(source) {
    document.querySelectorAll(".select-lead").forEach(cb => {
        cb.checked = source.checked;
    });
}

function deleteSelected() {
    const selected = [...document.querySelectorAll(".select-lead:checked")].map(cb => cb.value);

    if (selected.length === 0) {
        alert("No leads selected!");
        return;
    }

    if (!confirm(`Delete ${selected.length} leads?`)) return;

    fetch("/delete_multiple", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: selected })
    })
    .then(res => res.json())
    .then(() => location.reload());
}

/* ===========================================
   CHART IMPROVEMENT
   =========================================== */

function createChart(canvasId, labels, values, labelName) {
    const ctx = document.getElementById(canvasId).getContext("2d");

    new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: labelName,
                data: values,
                borderWidth: 3,
                borderColor: "rgba(255,255,255,0.9)",
                backgroundColor: "rgba(255,255,255,0.25)",
                tension: 0.4,
                fill: true,
                pointRadius: 4,
                pointBackgroundColor: "#fff"
            }]
        },
        options: {
            scales: {
                y: { beginAtZero: true }
            },
            plugins: {
                legend: { labels: { color: "#fff" } }
            }
        }
    });
}
