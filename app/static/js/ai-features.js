// AI Features JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Generate weekly report with confirmation
    const generateReportBtn = document.getElementById('generate-report-btn');
    if (generateReportBtn) {
        generateReportBtn.addEventListener('click', function(e) {
            if (!confirm('This will analyze your recent trades and generate a weekly report. Continue?')) {
                e.preventDefault();
            }
        });
    }
    
    // Mark news as read
    document.querySelectorAll('.mark-news-read').forEach(btn => {
        btn.addEventListener('click', async function() {
            const newsId = this.dataset.newsId;
            try {
                const response = await fetch(`/news/${newsId}/mark-read`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    this.closest('.news-item').classList.add('opacity-50');
                    this.remove();
                    updateUnreadCount();
                }
            } catch (error) {
                console.error('Error marking news as read:', error);
            }
        });
    });
    
    // Update unread news count
    async function updateUnreadCount() {
        try {
            const response = await fetch('/api/news?unread_only=true');
            if (response.ok) {
                const data = await response.json();
                const badge = document.getElementById('news-badge');
                if (badge) {
                    if (data.news.length > 0) {
                        badge.textContent = data.news.length;
                        badge.classList.remove('d-none');
                    } else {
                        badge.classList.add('d-none');
                    }
                }
            }
        } catch (error) {
            console.error('Error updating news count:', error);
        }
    }
    
    // Initialize
    updateUnreadCount();
    
    // Checklist functionality
    document.querySelectorAll('.checklist-item').forEach(item => {
        item.addEventListener('change', function() {
            const checklistId = this.closest('.checklist-card').dataset.checklistId;
            const itemId = this.dataset.itemId;
            const isChecked = this.checked;
            
            // Save state to localStorage
            const key = `checklist_${checklistId}_${itemId}`;
            localStorage.setItem(key, isChecked);
            
            // Update progress
            updateChecklistProgress(checklistId);
        });
    });
    
    // Initialize checklist states from localStorage
    document.querySelectorAll('.checklist-card').forEach(card => {
        const checklistId = card.dataset.checklistId;
        card.querySelectorAll('.checklist-item').forEach(item => {
            const itemId = item.dataset.itemId;
            const key = `checklist_${checklistId}_${itemId}`;
            const savedState = localStorage.getItem(key);
            if (savedState !== null) {
                item.checked = savedState === 'true';
            }
        });
        updateChecklistProgress(checklistId);
    });
    
    function updateChecklistProgress(checklistId) {
        const card = document.querySelector(`.checklist-card[data-checklist-id="${checklistId}"]`);
        const items = card.querySelectorAll('.checklist-item');
        const requiredItems = card.querySelectorAll('.checklist-item[data-required="true"]');
        
        const totalItems = items.length;
        const checkedItems = Array.from(items).filter(item => item.checked).length;
        const checkedRequired = Array.from(requiredItems).filter(item => item.checked).length;
        const totalRequired = requiredItems.length;
        
        const progress = (checkedItems / totalItems) * 100;
        const requiredProgress = totalRequired > 0 ? (checkedRequired / totalRequired) * 100 : 100;
        
        const progressBar = card.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            progressBar.textContent = `${Math.round(progress)}%`;
            
            // Color based on required items completion
            if (requiredProgress === 100) {
                progressBar.classList.remove('bg-warning', 'bg-danger');
                progressBar.classList.add('bg-success');
            } else if (requiredProgress >= 50) {
                progressBar.classList.remove('bg-success', 'bg-danger');
                progressBar.classList.add('bg-warning');
            } else {
                progressBar.classList.remove('bg-success', 'bg-warning');
                progressBar.classList.add('bg-danger');
            }
        }
    }
    
    // Risk-Reward chart (using Chart.js if available)
    if (typeof Chart !== 'undefined') {
        const ctx = document.getElementById('riskRewardChart');
        if (ctx) {
            new Chart(ctx.getContext('2d'), {
                type: 'scatter',
                data: window.riskRewardData || {
                    datasets: [{
                        label: 'Trades',
                        data: [],
                        backgroundColor: 'rgba(54, 162, 235, 0.6)'
                    }]
                },
                options: {
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Risk-Reward Ratio'
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Profit ($)'
                            }
                        }
                    }
                }
            });
        }
    }
});