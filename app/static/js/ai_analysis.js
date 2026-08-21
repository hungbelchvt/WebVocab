/**
 * WebVocab - AI Learning Analysis Frontend Controller
 * Interacts with /api/ai/learning-analysis to display real database stats
 * alongside Gemini 3.6 Flash structured educational insights.
 */

document.addEventListener('DOMContentLoaded', () => {
    // State Cards
    const loadingState = document.getElementById('ai-analysis-loading');
    const errorState = document.getElementById('ai-analysis-error');
    const errorMsg = document.getElementById('ai-analysis-error-msg');
    const retryBtn = document.getElementById('ai-analysis-retry-btn');
    const emptyState = document.getElementById('ai-analysis-empty');
    const resultsContainer = document.getElementById('ai-analysis-results');

    // Stat Cards Elements
    const statEnrolled = document.getElementById('stat-enrolled');
    const statAccuracy = document.getElementById('stat-accuracy');
    const statMastery = document.getElementById('stat-mastery');
    const statDue = document.getElementById('stat-due');

    // AI Overview Elements
    const aiSummaryText = document.getElementById('ai-summary-text');
    const strengthsList = document.getElementById('ai-strengths-list');
    const weaknessesList = document.getElementById('ai-weaknesses-list');
    const weakWordsList = document.getElementById('ai-weak-words-list');
    const weakTopicsList = document.getElementById('ai-weak-topics-list');
    const topicSection = document.getElementById('ai-topic-section');
    const insightsList = document.getElementById('ai-insights-list');
    const reviewPrioritiesWrap = document.getElementById('ai-review-priorities-wrap');

    // =================================================================
    // State Transitions
    // =================================================================
    function showState(stateName) {
        loadingState.style.display = (stateName === 'loading') ? 'block' : 'none';
        errorState.style.display = (stateName === 'error') ? 'block' : 'none';
        emptyState.style.display = (stateName === 'empty') ? 'block' : 'none';
        resultsContainer.style.display = (stateName === 'results') ? 'block' : 'none';
    }

    if (retryBtn) {
        retryBtn.addEventListener('click', loadAnalysis);
    }

    // =================================================================
    // Fetch & Load Analysis
    // =================================================================
    async function loadAnalysis() {
        showState('loading');

        try {
            const response = await fetch('/api/ai/learning-analysis');
            const data = await response.json();

            if (!response.ok || !data.success) {
                const message = (data.error && data.error.message) || data.message || 'Không thể tải phân tích học tập.';
                errorMsg.textContent = message;
                showState('error');
                return;
            }

            if (!data.has_data) {
                showState('empty');
                return;
            }

            renderDashboard(data.stats, data.analysis);
            showState('results');

        } catch (err) {
            console.error('AI Analysis Error:', err);
            errorMsg.textContent = 'Lỗi kết nối khi tải phân tích học tập. Vui lòng thử lại.';
            showState('error');
        }
    }

    // =================================================================
    // Render Dashboard
    // =================================================================
    function renderDashboard(stats, analysis) {
        // 1. Numerical Stat Cards
        statEnrolled.textContent = stats.total_words_enrolled || 0;
        statAccuracy.textContent = `${stats.overall_accuracy_percentage || 0}%`;
        statMastery.textContent = `${stats.total_mastered_words || 0} (${stats.mastery_percentage || 0}%)`;
        statDue.textContent = stats.total_due_reviews || 0;

        // 2. AI Summary
        aiSummaryText.textContent = analysis.summary || 'Đang theo dõi và phân tích tiến độ học tập của bạn.';

        // 3. Strengths
        strengthsList.innerHTML = '';
        if (analysis.strengths && analysis.strengths.length > 0) {
            analysis.strengths.forEach(str => {
                const li = document.createElement('li');
                li.innerHTML = `<i class="fa-solid fa-circle-check" style="color: #04AA6D;"></i> <span>${escapeHtml(str)}</span>`;
                strengthsList.appendChild(li);
            });
        } else {
            strengthsList.innerHTML = '<li><span style="color: #888;">Tiếp tục làm quiz để phát hiện các thế mạnh nổi bật.</span></li>';
        }

        // 4. Weaknesses
        weaknessesList.innerHTML = '';
        if (analysis.weaknesses && analysis.weaknesses.length > 0) {
            analysis.weaknesses.forEach(w => {
                const li = document.createElement('li');
                li.innerHTML = `<i class="fa-solid fa-triangle-exclamation" style="color: #f44336;"></i> <span>${escapeHtml(w)}</span>`;
                weaknessesList.appendChild(li);
            });
        } else {
            weaknessesList.innerHTML = '<li><span style="color: #888;">Chưa phát hiện điểm yếu nghiêm trọng nào.</span></li>';
        }

        // 5. Review Priorities (Tags)
        reviewPrioritiesWrap.innerHTML = '';
        if (analysis.review_priorities && analysis.review_priorities.length > 0) {
            analysis.review_priorities.forEach(word => {
                const pill = document.createElement('span');
                pill.className = 'ai-tag-pill';
                pill.style.borderColor = '#ff9800';
                pill.style.background = '#fff8e1';
                pill.style.color = '#e65100';
                pill.style.fontWeight = 'bold';
                pill.textContent = word;
                reviewPrioritiesWrap.appendChild(pill);
            });
        } else {
            reviewPrioritiesWrap.innerHTML = '<span style="color: #888; font-size: 0.9rem;">Không có từ vựng khẩn cấp cần ôn.</span>';
        }

        // 6. Weak Words Detailed Diagnosis
        weakWordsList.innerHTML = '';
        if (analysis.weak_words && analysis.weak_words.length > 0) {
            analysis.weak_words.forEach(item => {
                const card = document.createElement('div');
                card.className = 'ai-weak-word-card';
                card.innerHTML = `
                    <div class="ai-weak-word-head">
                        <span class="ai-weak-word-term">${escapeHtml(item.word)}</span>
                    </div>
                    <p class="ai-weak-word-issue"><i class="fa-solid fa-circle-exclamation" style="color: #f44336;"></i> ${escapeHtml(item.issue)}</p>
                    <p class="ai-weak-word-rec"><i class="fa-solid fa-lightbulb" style="color: #04AA6D;"></i> ${escapeHtml(item.recommendation)}</p>
                `;
                weakWordsList.appendChild(card);
            });
        } else {
            weakWordsList.innerHTML = '<p style="color: #888; font-style: italic;">Tuyệt vời! Bạn không có từ vựng nào bị đánh giá là yếu tại thời điểm này.</p>';
        }

        // 7. Topic Performance Cards
        weakTopicsList.innerHTML = '';
        if (stats.topic_stats && stats.topic_stats.length > 0) {
            topicSection.style.display = 'block';
            stats.topic_stats.forEach(t => {
                const card = document.createElement('div');
                card.className = 'w3-card';
                card.style.padding = '18px 22px';
                card.style.marginBottom = '14px';
                card.style.borderRadius = '8px';

                const accPct = Math.round(t.accuracy * 100);
                const badgeColor = t.is_weak ? '#f44336' : '#04AA6D';
                const badgeText = t.is_weak ? 'Cần cải thiện' : 'Tốt';

                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin: 0; font-size: 1.1rem; color: #222;">
                            <i class="fa-solid fa-folder" style="color: #04AA6D;"></i> ${escapeHtml(t.topic_name)}
                        </h4>
                        <span style="background: ${t.is_weak ? '#ffebee' : '#e8f5e9'}; color: ${badgeColor}; padding: 3px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: bold;">
                            ${badgeText} (${accPct}% đúng)
                        </span>
                    </div>
                    <div style="background: #e0e0e0; height: 6px; border-radius: 3px; overflow: hidden; margin-bottom: 8px;">
                        <div style="width: ${accPct}%; background: ${badgeColor}; height: 100%;"></div>
                    </div>
                    <p style="margin: 0; font-size: 0.85rem; color: #666;">
                        Tổng số: <strong>${t.total_words} từ</strong> | Đã kiểm tra: <strong>${t.tested_words} từ</strong> | Thành thạo: <strong>${t.mastered_words} từ</strong>
                    </p>
                `;
                weakTopicsList.appendChild(card);
            });
        } else {
            topicSection.style.display = 'none';
        }

        // 8. Actionable Insights
        insightsList.innerHTML = '';
        if (analysis.learning_insights && analysis.learning_insights.length > 0) {
            analysis.learning_insights.forEach(ins => {
                const item = document.createElement('div');
                item.className = 'ai-insight-item';
                item.innerHTML = `
                    <h4 class="ai-insight-title">
                        <i class="fa-solid fa-lightbulb" style="color: #ff9800;"></i> ${escapeHtml(ins.title)}
                    </h4>
                    <p class="ai-insight-desc">${escapeHtml(ins.insight)}</p>
                    <div class="ai-insight-action">
                        <i class="fa-solid fa-arrow-right" style="margin-right: 6px;"></i> <strong>Hành động đề xuất:</strong> ${escapeHtml(ins.action)}
                    </div>
                `;
                insightsList.appendChild(item);
            });
        }
    }

    function escapeHtml(str) {
        return (str || '')
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Initial Load
    loadAnalysis();
});
