/**
 * 备考助手 — 前端交互 JavaScript
 */

// ─── 任务打卡（循环切换状态）──────────────────────────

async function toggleTask(btn) {
    const taskId = btn.dataset.id;
    const currentStatus = btn.dataset.status;

    // 状态循环: pending → partial → completed → skipped → pending
    const statusCycle = {
        'pending': 'partial',
        'partial': 'completed',
        'completed': 'skipped',
        'skipped': 'pending',
        'confirmed': 'partial',  // 已确认的任务
    };

    const nextStatus = statusCycle[currentStatus] || 'completed';

    try {
        const resp = await fetch(`/api/task/${taskId}/check`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: nextStatus }),
        });
        const data = await resp.json();

        if (data.ok) {
            // 更新按钮图标
            const icons = {
                'pending': '⬜',
                'partial': '🔶',
                'completed': '✅',
                'skipped': '⏭',
                'confirmed': '⬜',
            };
            btn.textContent = icons[nextStatus] || '✅';
            btn.dataset.status = nextStatus;

            // 更新任务项的样式
            const taskItem = btn.closest('.task-item');
            taskItem.className = taskItem.className.replace(/status-\w+/g, `status-${nextStatus}`);

            // 更新标题样式
            const title = taskItem.querySelector('.task-title');
            if (title) {
                title.classList.toggle('done', nextStatus === 'completed');
                title.classList.toggle('skipped', nextStatus === 'skipped');
            }

            // 更新整体进度条
            updateProgress();
        }
    } catch (e) {
        console.error('打卡失败:', e);
    }
}


// ─── 更新主页进度条 ─────────────────────────────────

function updateProgress() {
    const taskItems = document.querySelectorAll('.task-item');
    let total = 0, completed = 0, partial = 0;

    taskItems.forEach(item => {
        const btn = item.querySelector('.check-btn');
        if (btn) {
            total++;
            if (btn.dataset.status === 'completed') completed++;
            if (btn.dataset.status === 'partial') partial++;
        }
    });

    if (total === 0) return;

    const pct = ((completed + partial * 0.5) / total) * 100;

    const bar = document.querySelector('.progress-bar');
    const text = document.querySelector('.progress-text');

    if (bar) bar.style.width = pct + '%';
    if (text) {
        let statusText = `完成 ${completed}/${total}`;
        if (partial > 0) statusText += `（${partial} 项进行中）`;
        if (completed === total) statusText = '🎉 全部完成！';
        text.textContent = statusText;
    }
}


// ─── PWA 注册（可选）─────────────────────────────────

if ('serviceWorker' in navigator) {
    // 后续可添加 service worker 实现离线缓存
}
