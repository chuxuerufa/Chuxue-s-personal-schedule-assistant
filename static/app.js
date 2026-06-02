/**
 * Study Planner — Linear style interactions
 */

// ─── User key helpers ───────────────────────────────

function getUserHeaders() {
    var h = {};
    var ds = localStorage.getItem('user_ds_key');
    var fs = localStorage.getItem('user_fs_url');
    if (ds) h['X-User-DS-Key'] = ds;
    if (fs) h['X-User-FS-URL'] = fs;
    return h;
}

// ─── Task toggle (Linear checkbox) ──────────────────

async function toggleTask(btn) {
    const taskId = btn.dataset.id;
    const current = btn.dataset.status;
    const cycle = {
        'pending': 'partial', 'partial': 'completed',
        'completed': 'skipped', 'skipped': 'pending',
        'confirmed': 'partial',
    };
    const next = cycle[current] || 'completed';

    btn.style.transform = 'scale(0.85)';
    setTimeout(() => btn.style.transform = '', 150);

    try {
        const resp = await fetch(`/api/task/${taskId}/check`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: next }),
        });
        const data = await resp.json();
        if (data.ok) {
            btn.className = btn.className.replace(/status-\w+/g, `status-${next}`);
            btn.dataset.status = next;

            const row = btn.closest('.task-row');
            if (row) row.className = row.className.replace(/status-\w+/g, `status-${next}`);

            const title = row ? row.querySelector('.task-title') : null;
            if (title) {
                title.classList.toggle('done', next === 'completed');
                title.classList.toggle('skipped', next === 'skipped');
            }
            updateProgress();
        }
    } catch (e) { console.error('Toggle failed:', e); }
}

// ─── Update progress bar ────────────────────────────

function updateProgress() {
    const rows = document.querySelectorAll('.task-row');
    let total = 0, completed = 0, partial = 0;
    rows.forEach(row => {
        const check = row.querySelector('.ln-check');
        if (!check) return;
        total++;
        if (check.dataset.status === 'completed') completed++;
        if (check.dataset.status === 'partial') partial++;
    });
    if (!total) return;

    const pct = Math.round((completed + partial * 0.5) / total * 100);
    const fill = document.querySelector('.progress-fill');
    const pctEl = document.querySelector('.progress-pct');
    if (fill) fill.style.width = pct + '%';
    if (pctEl) pctEl.textContent = `${pct}% · ${completed}/${total}`;
}

// ─── Add task form toggle ───────────────────────────

function toggleAddForm() {
    const form = document.getElementById('inlineAddForm');
    const btn = document.getElementById('showAddFormBtn');
    const addBtn = document.getElementById('addBtn');
    form.classList.toggle('open');
    const isOpen = form.classList.contains('open');
    if (btn) btn.textContent = isOpen ? '− 取消' : '+ 添加任务';
    if (addBtn) addBtn.textContent = isOpen ? '×' : '+';
    if (isOpen) {
        const inp = document.getElementById('newTaskTitle');
        if (inp) setTimeout(() => inp.focus(), 280);
    }
}

async function addNewTask() {
    const title = document.getElementById('newTaskTitle').value.trim();
    if (!title) { alert('请输入任务标题'); return; }
    const subject = document.getElementById('newTaskSubject').value;
    const minutes = parseInt(document.getElementById('newTaskMinutes').value) || 45;
    const priority = document.getElementById('newTaskPriority').value;

    const submitBtn = document.querySelector('#inlineAddForm .btn.primary');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = '添加中...'; }

    try {
        const resp = await fetch('/api/task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, subject, estimated_minutes: minutes, priority }),
        });
        const data = await resp.json();
        if (data.ok) location.reload();
        else { alert('添加失败：' + (data.error || '')); if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '添加'; } }
    } catch (e) {
        alert('请求失败：' + e.message);
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '添加'; }
    }
}

// ─── Delete task ─────────────────────────────────────

async function deleteTask(btn, taskId) {
    if (!confirm('确定删除此任务？')) return;
    btn.disabled = true;
    try {
        const resp = await fetch(`/api/task/${taskId}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.ok) {
            const row = btn.closest('.task-row');
            row.style.transition = 'opacity 0.15s ease';
            row.style.opacity = '0';
            setTimeout(() => { row.remove(); updateProgress(); }, 150);
        } else { alert('删除失败：' + (data.error || '')); btn.disabled = false; }
    } catch (e) { alert('请求失败：' + e.message); btn.disabled = false; }
}

// ─── Inline title edit ───────────────────────────────

function startEditTitle(spanEl) {
    const taskId = spanEl.dataset.taskId;
    const current = spanEl.textContent.trim();
    const input = document.createElement('input');
    input.type = 'text'; input.value = current;
    input.className = 'task-title-input-inline';
    spanEl.replaceWith(input);
    input.focus(); input.select();

    const save = async () => {
        const val = input.value.trim();
        if (val && val !== current) {
            try {
                const resp = await fetch(`/api/task/${taskId}`, {
                    method: 'PUT', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: val }),
                });
                const data = await resp.json();
                if (data.ok) {
                    const s = document.createElement('span');
                    s.className = spanEl.className; s.textContent = val;
                    s.dataset.taskId = taskId; s.onclick = () => startEditTitle(s);
                    input.replaceWith(s);
                } else { alert('更新失败'); input.replaceWith(spanEl); }
            } catch (e) { alert('请求失败'); input.replaceWith(spanEl); }
        } else { input.replaceWith(spanEl); }
    };
    input.addEventListener('blur', save);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') input.blur();
        if (e.key === 'Escape') { input.value = current; input.blur(); }
    });
}
