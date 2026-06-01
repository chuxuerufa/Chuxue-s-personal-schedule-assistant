/**
 * 备考助手 — iOS HIG 风格交互
 */

// ─── 任务打卡（iOS 圆形勾选框）────────────────────

async function toggleTask(btn) {
    const taskId = btn.dataset.id;
    const currentStatus = btn.dataset.status;

    const cycle = {
        'pending': 'partial',
        'partial': 'completed',
        'completed': 'skipped',
        'skipped': 'pending',
        'confirmed': 'partial',
    };
    const next = cycle[currentStatus] || 'completed';

    // 轻触缩放反馈
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

            const title = row ? row.querySelector('.task-title-text') : null;
            if (title) {
                title.classList.toggle('done', next === 'completed');
                title.classList.toggle('skipped', next === 'skipped');
            }
            updateRing();
        }
    } catch (e) { console.error('打卡失败:', e); }
}


// ─── 更新 SVG 进度环 ─────────────────────────────

function updateRing() {
    const rows = document.querySelectorAll('.task-row');
    let total = 0, completed = 0, partial = 0;
    rows.forEach(row => {
        const check = row.querySelector('.ios-check');
        if (!check) return;
        total++;
        if (check.dataset.status === 'completed') completed++;
        if (check.dataset.status === 'partial') partial++;
    });
    if (!total) return;

    const pct = Math.round((completed + partial * 0.5) / total * 100);
    const c = 276.46;
    const o = c * (1 - pct / 100);

    const ring = document.querySelector('.ring-fill');
    const pctEl = document.querySelector('.ring-pct');
    const subEl = document.querySelector('.ring-sub');
    if (ring) { ring.style.strokeDasharray = c; ring.style.strokeDashoffset = o; }
    if (pctEl) pctEl.textContent = pct + '%';
    if (subEl) subEl.textContent = `${completed}/${total}`;
}


// ─── 添加任务面板 ────────────────────────────────

function toggleAddForm() {
    const form = document.getElementById('inlineAddForm');
    const btn = document.getElementById('showAddFormBtn');
    const addBtn = document.getElementById('addBtn');
    form.classList.toggle('open');
    const isOpen = form.classList.contains('open');
    if (btn) btn.textContent = isOpen ? '− 收起' : '+ 添加任务';
    if (addBtn) addBtn.textContent = isOpen ? '关闭' : '+ 添加';
    if (isOpen) {
        const inp = document.getElementById('newTaskTitle');
        if (inp) setTimeout(() => inp.focus(), 350);
    }
}

async function addNewTask() {
    const title = document.getElementById('newTaskTitle').value.trim();
    if (!title) { alert('请输入任务标题'); return; }

    const subject = document.getElementById('newTaskSubject').value;
    const minutes = parseInt(document.getElementById('newTaskMinutes').value) || 45;
    const priority = document.getElementById('newTaskPriority').value;

    const btn = document.querySelector('#inlineAddForm .btn-ios.primary');
    if (btn) { btn.disabled = true; btn.textContent = '添加中…'; }

    try {
        const resp = await fetch('/api/task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, subject, estimated_minutes: minutes, priority }),
        });
        const data = await resp.json();
        if (data.ok) location.reload();
        else alert('添加失败：' + (data.error || ''));
    } catch (e) {
        alert('请求失败：' + e.message);
        if (btn) { btn.disabled = false; btn.textContent = '添加'; }
    }
}


// ─── 删除任务 ────────────────────────────────────

async function deleteTask(btn, taskId) {
    if (!confirm('确定删除吗？')) return;
    btn.disabled = true;
    try {
        const resp = await fetch(`/api/task/${taskId}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.ok) {
            const row = btn.closest('.task-row');
            row.style.transition = 'opacity 0.2s ease';
            row.style.opacity = '0';
            setTimeout(() => { row.remove(); updateRing(); }, 200);
        } else {
            alert('删除失败：' + (data.error || ''));
            btn.disabled = false;
        }
    } catch (e) {
        alert('请求失败：' + e.message);
        btn.disabled = false;
    }
}


// ─── 内联编辑标题 ────────────────────────────────

function startEditTitle(spanEl) {
    const taskId = spanEl.dataset.taskId;
    const current = spanEl.textContent.trim();
    const input = document.createElement('input');
    input.type = 'text';
    input.value = current;
    input.className = 'task-title-input-inline';
    spanEl.replaceWith(input);
    input.focus(); input.select();

    const save = async () => {
        const val = input.value.trim();
        if (val && val !== current) {
            try {
                const resp = await fetch(`/api/task/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: val }),
                });
                const data = await resp.json();
                if (data.ok) {
                    const s = document.createElement('span');
                    s.className = spanEl.className;
                    s.textContent = val;
                    s.dataset.taskId = taskId;
                    s.onclick = () => startEditTitle(s);
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
