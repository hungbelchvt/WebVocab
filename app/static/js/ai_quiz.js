/**
 * WebVocab - AI Quiz Generator Frontend Controller
 * Interacts with /api/ai/quiz to generate personalized questions
 * and /api/submit_quiz_batch to update real user WordProgress and XP.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Setup Section Elements
    const setupCard = document.getElementById('ai-quiz-setup-card');
    const generateBtn = document.getElementById('ai-quiz-generate-btn');
    const topicSelect = document.getElementById('ai-quiz-topic-select');
    const countBtns = document.querySelectorAll('.ai-count-btn');
    let selectedCount = 5;

    // State Cards
    const loadingState = document.getElementById('ai-quiz-loading-state');
    const errorState = document.getElementById('ai-quiz-error-state');
    const errorMsg = document.getElementById('ai-quiz-error-msg');
    const retryBtn = document.getElementById('ai-quiz-retry-btn');
    const quizContainer = document.getElementById('ai-quiz-container');

    // Runner Elements
    const progressText = document.getElementById('ai-quiz-progress-text');
    const progressFill = document.getElementById('ai-quiz-progress-fill');
    const typeBadge = document.getElementById('ai-quiz-type-badge');
    const questionTitle = document.getElementById('ai-quiz-question-title');
    const optionsContainer = document.getElementById('ai-quiz-options');
    const explanationBox = document.getElementById('ai-quiz-explanation');
    const explanationText = document.getElementById('ai-quiz-explanation-text');
    const nextBtn = document.getElementById('ai-quiz-next-btn');

    let questionsData = [];
    let currentIndex = 0;
    let quizResults = [];
    let isAnswered = false;

    // =================================================================
    // Load Topics for Setup Dropdown
    // =================================================================
    async function loadTopics() {
        try {
            const res = await fetch('/api/ai/topics');
            const data = await res.json();
            if (data.success && data.topics) {
                topicSelect.innerHTML = '<option value="all">-- Tất cả từ vựng đang học --</option>';
                data.topics.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t.id;
                    opt.textContent = `${t.name} (${t.word_count} từ)`;
                    topicSelect.appendChild(opt);
                });
            }
        } catch (e) {
            console.error('Failed to load topics for quiz setup:', e);
        }
    }

    loadTopics();

    // =================================================================
    // Question Count Selector
    // =================================================================
    countBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            countBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedCount = parseInt(btn.getAttribute('data-count') || '5');
        });
    });

    // =================================================================
    // State Transitions
    // =================================================================
    function showState(stateName) {
        setupCard.style.display = (stateName === 'setup') ? 'block' : 'none';
        loadingState.style.display = (stateName === 'loading') ? 'block' : 'none';
        errorState.style.display = (stateName === 'error') ? 'block' : 'none';
        quizContainer.style.display = (stateName === 'quiz') ? 'block' : 'none';

        if (stateName === 'loading') {
            generateBtn.disabled = true;
        } else {
            generateBtn.disabled = false;
        }
    }

    // =================================================================
    // API Call: Generate AI Quiz
    // =================================================================
    generateBtn.addEventListener('click', async () => {
        const topicId = topicSelect.value;
        await startAIQuiz(topicId, selectedCount);
    });

    if (retryBtn) {
        retryBtn.addEventListener('click', () => {
            showState('setup');
        });
    }

    async function startAIQuiz(topicId, count) {
        showState('loading');

        try {
            const response = await fetch('/api/ai/quiz', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    topic_id: topicId,
                    question_count: count
                })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                const message = (data.error && data.error.message) || data.message || 'Không thể tạo quiz lúc này. Vui lòng thử lại.';
                errorMsg.textContent = message;
                showState('error');
                return;
            }

            questionsData = data.questions || [];
            if (questionsData.length === 0) {
                errorMsg.textContent = 'Không có câu hỏi nào được tạo. Vui lòng thêm từ vựng trước.';
                showState('error');
                return;
            }

            // Reset quiz runner
            currentIndex = 0;
            quizResults = [];
            showState('quiz');
            renderQuestion(currentIndex);

        } catch (err) {
            console.error('AI Quiz Fetch Error:', err);
            errorMsg.textContent = 'Lỗi kết nối khi gọi AI. Vui lòng kiểm tra mạng và thử lại.';
            showState('error');
        }
    }

    // =================================================================
    // Render Active Question
    // =================================================================
    function renderQuestion(index) {
        isAnswered = false;
        const q = questionsData[index];
        const total = questionsData.length;

        // Progress bar & text
        progressText.textContent = `Câu hỏi ${index + 1} / ${total}`;
        const pct = Math.round(((index + 1) / total) * 100);
        progressFill.style.width = `${pct}%`;

        // Type Badge
        const typeLabels = {
            'multiple_choice': 'Nghĩa của từ',
            'fill_blank': 'Điền vào chỗ trống',
            'context': 'Ngữ cảnh thực tế'
        };
        typeBadge.textContent = typeLabels[q.type] || 'Trắc nghiệm từ vựng';
        typeBadge.className = `ai-quiz-type-badge ${q.type || 'multiple_choice'}`;

        // Question Title
        questionTitle.textContent = q.question;

        // Hide explanation & Next button initially
        explanationBox.style.display = 'none';
        nextBtn.style.display = 'none';
        nextBtn.textContent = (index === total - 1) ? 'Hoàn thành & Xem kết quả' : 'Câu tiếp theo';

        // Options
        optionsContainer.innerHTML = '';
        const alphabet = ['A', 'B', 'C', 'D'];

        q.options.forEach((opt, idx) => {
            const btn = document.createElement('button');
            btn.className = 'ai-quiz-opt-btn';
            btn.setAttribute('data-id', opt.id);
            btn.innerHTML = `
                <span style="font-weight: bold; color: #04AA6D; width: 24px;">${alphabet[idx] || (idx + 1)}.</span>
                <span style="flex-grow: 1;">${escapeHtml(opt.def)}</span>
            `;

            btn.addEventListener('click', () => {
                handleOptionClick(btn, opt.id, q.correct_id, q);
            });

            optionsContainer.appendChild(btn);
        });
    }

    // =================================================================
    // Handle Option Selection
    // =================================================================
    function handleOptionClick(button, selectedId, correctId, questionData) {
        if (isAnswered) return;
        isAnswered = true;

        const allButtons = optionsContainer.querySelectorAll('.ai-quiz-opt-btn');
        allButtons.forEach(b => {
            b.disabled = true;
            b.style.cursor = 'default';
        });

        const isCorrect = (selectedId === correctId);

        if (isCorrect) {
            button.classList.add('correct');
        } else {
            button.classList.add('incorrect');
            // Highlight the correct option in green
            allButtons.forEach(b => {
                if (parseInt(b.getAttribute('data-id')) === correctId) {
                    b.classList.add('correct');
                }
            });
        }

        // Show Explanation
        explanationText.textContent = questionData.explanation || 'Không có giải thích chi tiết.';
        explanationBox.className = `ai-quiz-explanation ${isCorrect ? '' : 'error-exp'}`;
        explanationBox.style.display = 'block';

        // Record result for submit_quiz_batch
        quizResults.push({
            progress_id: questionData.progress_id,
            is_correct: isCorrect,
            term: questionData.word || questionData.target_term,
            options: questionData.options,
            correct_id: correctId,
            selected_id: selectedId
        });

        // Reveal Next button
        nextBtn.style.display = 'inline-flex';
    }

    // =================================================================
    // Next Button Click & Batch Submission
    // =================================================================
    nextBtn.addEventListener('click', async () => {
        if (currentIndex < questionsData.length - 1) {
            currentIndex++;
            renderQuestion(currentIndex);
        } else {
            // Last question answered -> Submit to existing WebVocab endpoint
            nextBtn.disabled = true;
            nextBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Đang lưu kết quả...';

            try {
                const response = await fetch('/api/submit_quiz_batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ results: quizResults })
                });

                const data = await response.json();
                if (data.status === 'success' && data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    window.location.href = '/dashboard';
                }
            } catch (e) {
                console.error('Quiz submit batch error:', e);
                window.location.href = '/dashboard';
            }
        }
    });

    function escapeHtml(str) {
        return (str || '')
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
