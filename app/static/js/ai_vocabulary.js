/**
 * WebVocab - AI Vocabulary Assistant Frontend Controller
 * Interacts with /api/ai/vocabulary and /api/ai/vocabulary/add-to-topic
 */

document.addEventListener('DOMContentLoaded', () => {
    // Form & Input elements
    const form = document.getElementById('ai-vocab-form');
    const wordInput = document.getElementById('ai-word-input');
    const submitBtn = document.getElementById('ai-submit-btn');
    const quickChips = document.querySelectorAll('.quick-chip');

    // State Cards
    const emptyState = document.getElementById('ai-empty-state');
    const loadingState = document.getElementById('ai-loading-state');
    const errorState = document.getElementById('ai-error-state');
    const errorMsg = document.getElementById('ai-error-msg');
    const retryBtn = document.getElementById('ai-retry-btn');
    const resultContainer = document.getElementById('ai-result-container');

    // Result Elements
    const wordTerm = document.getElementById('res-word-term');
    const wordPos = document.getElementById('res-word-pos');
    const wordIpa = document.getElementById('res-word-ipa');
    const audioBtn = document.getElementById('res-audio-btn');
    const meaningText = document.getElementById('res-meaning-text');
    const examplesList = document.getElementById('res-examples-list');
    const synonymsWrap = document.getElementById('res-synonyms-wrap');
    const antonymsWrap = document.getElementById('res-antonyms-wrap');
    const collocationsWrap = document.getElementById('res-collocations-wrap');
    const memoryTipText = document.getElementById('res-memory-tip-text');
    const addDeckBtn = document.getElementById('res-add-deck-btn');

    // Modal Elements
    const modal = document.getElementById('ai-add-modal');
    const modalCloseBtn = document.getElementById('ai-modal-close-btn');
    const modalCancelBtn = document.getElementById('ai-modal-cancel-btn');
    const modalSubmitBtn = document.getElementById('ai-modal-submit-btn');
    const topicSelect = document.getElementById('ai-topic-select');
    const newTopicGroup = document.getElementById('ai-new-topic-group');
    const newTopicInput = document.getElementById('ai-new-topic-input');
    const modalAlert = document.getElementById('ai-modal-alert');

    let currentAnalysisData = null;
    let lastSearchedWord = '';

    // =================================================================
    // TTS Audio Helper
    // =================================================================
    function playAudio(text) {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'en-US';
            utterance.rate = 0.9;
            window.speechSynthesis.speak(utterance);
        }
    }

    if (audioBtn) {
        audioBtn.addEventListener('click', () => {
            if (currentAnalysisData && currentAnalysisData.word) {
                playAudio(currentAnalysisData.word);
            }
        });
    }

    // =================================================================
    // State Transitions
    // =================================================================
    function showState(stateName) {
        emptyState.style.display = (stateName === 'empty') ? 'block' : 'none';
        loadingState.style.display = (stateName === 'loading') ? 'block' : 'none';
        errorState.style.display = (stateName === 'error') ? 'block' : 'none';
        resultContainer.style.display = (stateName === 'result') ? 'block' : 'none';

        if (stateName === 'loading') {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Đang phân tích...';
        } else {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Phân tích';
        }
    }

    // =================================================================
    // API Call: Analyze Vocabulary
    // =================================================================
    async function analyzeWord(word) {
        const cleanWord = (word || '').trim();
        if (!cleanWord) {
            wordInput.focus();
            return;
        }

        lastSearchedWord = cleanWord;
        showState('loading');

        try {
            const response = await fetch('/api/ai/vocabulary', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ word: cleanWord })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                const message = (data.error && data.error.message) || data.message || 'Không thể phân tích từ vựng lúc này. Vui lòng thử lại.';
                errorMsg.textContent = message;
                showState('error');
                return;
            }

            currentAnalysisData = data.data;
            renderResult(data.data);
            showState('result');

        } catch (err) {
            console.error('AI Vocab Fetch Error:', err);
            errorMsg.textContent = 'Lỗi kết nối hoặc yêu cầu quá thời gian. Vui lòng kiểm tra mạng và thử lại.';
            showState('error');
        }
    }

    // =================================================================
    // Render Result
    // =================================================================
    function renderResult(data) {
        wordTerm.textContent = data.word || '';
        wordPos.textContent = data.part_of_speech || '';
        wordIpa.textContent = data.pronunciation || '';
        meaningText.textContent = data.meaning_vi || '';

        // Examples
        examplesList.innerHTML = '';
        if (data.examples && data.examples.length > 0) {
            data.examples.forEach(ex => {
                const item = document.createElement('div');
                item.className = 'ai-example-item';
                item.innerHTML = `
                    <p class="ai-example-sentence">${escapeHtml(ex.sentence || '')}</p>
                    <p class="ai-example-trans">${escapeHtml(ex.translation_vi || '')}</p>
                `;
                examplesList.appendChild(item);
            });
        } else {
            examplesList.innerHTML = '<p style="color: #888;">Chưa có ví dụ cho từ này.</p>';
        }

        // Synonyms
        renderPills(synonymsWrap, data.synonyms, 'synonym', 'Không có từ đồng nghĩa phổ biến.');

        // Antonyms
        renderPills(antonymsWrap, data.antonyms, 'antonym', 'Không có từ trái nghĩa phổ biến.');

        // Collocations
        renderPills(collocationsWrap, data.collocations, 'collocation', 'Không có cụm từ mẫu.');

        // Memory Tip
        if (data.memory_tip) {
            memoryTipText.textContent = data.memory_tip;
            document.getElementById('ai-memory-tip-card').style.display = 'flex';
        } else {
            document.getElementById('ai-memory-tip-card').style.display = 'none';
        }

        // Reset Add Button state
        addDeckBtn.disabled = false;
        addDeckBtn.innerHTML = '<i class="fa-solid fa-plus"></i> Thêm vào danh sách từ vựng';
        addDeckBtn.style.background = '#04AA6D';
    }

    function renderPills(container, items, className, emptyMsg) {
        container.innerHTML = '';
        if (items && items.length > 0) {
            items.forEach(text => {
                const pill = document.createElement('span');
                pill.className = `ai-tag-pill ${className}`;
                pill.textContent = text;
                container.appendChild(pill);
            });
        } else {
            container.innerHTML = `<span style="color: #999; font-size: 0.85rem;">${emptyMsg}</span>`;
        }
    }

    function escapeHtml(str) {
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // =================================================================
    // Event Listeners: Form & Quick Chips
    // =================================================================
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        analyzeWord(wordInput.value);
    });

    quickChips.forEach(chip => {
        chip.addEventListener('click', () => {
            const word = chip.getAttribute('data-word') || chip.textContent;
            wordInput.value = word.trim();
            analyzeWord(word);
        });
    });

    if (retryBtn) {
        retryBtn.addEventListener('click', () => {
            if (lastSearchedWord) {
                analyzeWord(lastSearchedWord);
            }
        });
    }

    // =================================================================
    // Modal: Add to Vocabulary Deck
    // =================================================================
    if (addDeckBtn) {
        addDeckBtn.addEventListener('click', () => {
            openAddModal();
        });
    }

    async function openAddModal() {
        if (!currentAnalysisData) return;

        modalAlert.style.display = 'none';
        modalSubmitBtn.disabled = false;
        modalSubmitBtn.textContent = 'Lưu từ';
        newTopicInput.value = '';

        // Load available topics
        topicSelect.innerHTML = '<option value="">-- Đang tải danh mục... --</option>';
        modal.style.display = 'flex';

        try {
            const res = await fetch('/api/ai/topics');
            const data = await res.json();

            topicSelect.innerHTML = '';

            if (data.success && data.topics && data.topics.length > 0) {
                topicSelect.innerHTML += '<option value="">-- Chọn một danh mục có sẵn --</option>';
                data.topics.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t.id;
                    opt.textContent = `${t.name} (${t.word_count} từ)`;
                    topicSelect.appendChild(opt);
                });
                topicSelect.innerHTML += '<option value="__new__">+ Tạo danh mục mới...</option>';
                newTopicGroup.style.display = 'none';
            } else {
                topicSelect.innerHTML = '<option value="__new__">+ Tạo danh mục mới đầu tiên...</option>';
                newTopicGroup.style.display = 'block';
                newTopicInput.focus();
            }

        } catch (e) {
            topicSelect.innerHTML = '<option value="__new__">+ Tạo danh mục mới...</option>';
            newTopicGroup.style.display = 'block';
        }
    }

    topicSelect.addEventListener('change', () => {
        if (topicSelect.value === '__new__') {
            newTopicGroup.style.display = 'block';
            newTopicInput.focus();
        } else {
            newTopicGroup.style.display = 'none';
        }
    });

    function closeAddModal() {
        modal.style.display = 'none';
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeAddModal);
    if (modalCancelBtn) modalCancelBtn.addEventListener('click', closeAddModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeAddModal();
    });

    // Save Word to Topic
    modalSubmitBtn.addEventListener('click', async () => {
        if (!currentAnalysisData) return;

        modalAlert.style.display = 'none';

        const selectedVal = topicSelect.value;
        let topicId = null;
        let newTopicName = null;

        if (selectedVal === '__new__' || !selectedVal) {
            newTopicName = newTopicInput.value.trim();
            if (!newTopicName) {
                showModalAlert('Vui lòng nhập tên danh mục mới.', 'error');
                newTopicInput.focus();
                return;
            }
        } else {
            topicId = parseInt(selectedVal);
        }

        modalSubmitBtn.disabled = true;
        modalSubmitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Đang lưu...';

        try {
            const payload = {
                topic_id: topicId,
                new_topic_name: newTopicName,
                word: currentAnalysisData.word,
                pronunciation: currentAnalysisData.pronunciation,
                meaning_vi: currentAnalysisData.meaning_vi,
                examples: currentAnalysisData.examples,
                synonyms: currentAnalysisData.synonyms,
                antonyms: currentAnalysisData.antonyms
            };

            const response = await fetch('/api/ai/vocabulary/add-to-topic', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const resData = await response.json();

            if (!response.ok || !resData.success) {
                showModalAlert(resData.error || resData.message || 'Không thể thêm từ vào danh mục.', 'error');
                modalSubmitBtn.disabled = false;
                modalSubmitBtn.textContent = 'Lưu từ';
                return;
            }

            // Success
            showModalAlert(resData.message || 'Đã thêm từ thành công!', 'success');
            addDeckBtn.disabled = true;
            addDeckBtn.innerHTML = '<i class="fa-solid fa-check"></i> Đã có trong danh sách';
            addDeckBtn.style.background = '#81c784';

            setTimeout(() => {
                closeAddModal();
            }, 1200);

        } catch (err) {
            console.error('Error adding word:', err);
            showModalAlert('Lỗi mạng khi lưu từ. Vui lòng thử lại.', 'error');
            modalSubmitBtn.disabled = false;
            modalSubmitBtn.textContent = 'Lưu từ';
        }
    });

    function showModalAlert(message, type) {
        modalAlert.textContent = message;
        modalAlert.className = `ai-modal-alert ${type}`;
        modalAlert.style.display = 'block';
    }
});
