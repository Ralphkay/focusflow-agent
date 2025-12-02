document.addEventListener('DOMContentLoaded', () => {
    // --- API Endpoints ---
    const ANALYTICS_ENDPOINT = '/api/dashboard-analytics';
    const HEALTH_ENDPOINT = '/api/health';

    // --- Chart instances ---
    let activityChart;
    let productivityChart;

    // --- Utility Functions ---
    const formatMinutes = (minutes) => {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return `${hours}h ${mins}m`;
    };

    const updateStatusIndicator = (isOnline) => {
        const indicator = document.getElementById('status-indicator');
        if (isOnline) {
            indicator.classList.add('online');
            indicator.title = 'Connected to Central Server';
        } else {
            indicator.classList.remove('online');
            indicator.title = 'Failed to connect to Central Server';
        }
    };

    // --- Data Fetching Functions ---
    const fetchHealthStatus = async () => {
        try {
            const response = await fetch(HEALTH_ENDPOINT);
            updateStatusIndicator(response.ok);
        } catch (error) {
            console.error('Failed to fetch health status:', error);
            updateStatusIndicator(false);
        }
    };

    const fetchAnalyticsData = async () => {
        try {
            const response = await fetch(ANALYTICS_ENDPOINT + '?time_period=7');
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            const data = await response.json();
            console.log("Fetched analytics data:", data);
            return data;
        } catch (error) {
            console.error('Failed to fetch dashboard analytics data:', error);
            return null;
        }
    };

    const updateDashboard = async () => {
        const data = await fetchAnalyticsData();
        if (!data) {
            document.getElementById('overall-insight').textContent = "Could not load data from the server.";
            document.getElementById('tasks-list').textContent = "Could not load tasks.";
            return;
        }

        // Update Summary Cards
        document.getElementById('active-time').textContent = formatMinutes(data.summary.total_active_time_minutes_today);
        document.getElementById('productivity-score').textContent = `${(data.summary.average_productivity_score_last_7_days * 100).toFixed(0)}%`;
        document.getElementById('keystrokes').textContent = data.summary.keystrokes_today;
        document.getElementById('clicks').textContent = data.summary.clicks_today;
        document.getElementById('overall-insight').textContent = data.insights.overall_insight || 'No insights available yet.';

        // Update Charts
        updateCharts(data.activity_trend, data.productivity_trend);

        // Update Tasks List
        updateTasks(data.tasks);
    };

    const updateCharts = (activityData, productivityData) => {
        const labels = activityData.map(d => d.date);
        const activeTime = activityData.map(d => d.total_active_time_minutes);
        const idleTime = activityData.map(d => d.total_idle_time_minutes);
        const productivityScores = productivityData.map(d => (d.productivity_score * 100).toFixed(0));

        // Destroy old charts to prevent redraw issues
        if (activityChart) activityChart.destroy();
        if (productivityChart) productivityChart.destroy();

        // Daily Activity Chart
        const activityCtx = document.getElementById('activityChart').getContext('2d');
        activityChart = new Chart(activityCtx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Active Time (minutes)',
                        data: activeTime,
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    },
                    {
                        label: 'Idle Time (minutes)',
                        data: idleTime,
                        backgroundColor: 'rgba(255, 99, 132, 0.7)',
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true }
                }
            }
        });

        // Productivity Trend Chart
        const productivityCtx = document.getElementById('productivityChart').getContext('2d');
        productivityChart = new Chart(productivityCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Productivity Score (%)',
                        data: productivityScores,
                        borderColor: '#007bff',
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    };

    const updateTasks = (tasks) => {
        const tasksList = document.getElementById('tasks-list');
        tasksList.innerHTML = '';
        if (tasks.length === 0) {
            tasksList.innerHTML = '<p>No tasks assigned to you.</p>';
            return;
        }

        tasks.forEach(task => {
            const taskItem = document.createElement('div');
            taskItem.className = 'task-item';
            taskItem.innerHTML = `
                <h3>${task.task_name}</h3>
                <p><strong>Project:</strong> ${task.project_name}</p>
                <p><strong>Status:</strong> ${task.status}</p>
                <p><strong>Due Date:</strong> ${task.due_date || 'N/A'}</p>
                <button onclick="fetchTaskActivities(${task.id})">Show Activities</button>
                <div id="activities-${task.id}" class="activities-list" style="display:none;"></div>
            `;
            tasksList.appendChild(taskItem);
        });
    };

    // --- Global function to be called from HTML ---
    window.fetchTaskActivities = async (taskId) => {
        const activitiesContainer = document.getElementById(`activities-${taskId}`);
        activitiesContainer.style.display = activitiesContainer.style.display === 'block' ? 'none' : 'block';

        if (activitiesContainer.style.display === 'block') {
            activitiesContainer.innerHTML = 'Loading activities...';
            try {
                const response = await fetch(`/api/task/${taskId}/activities`);
                const activities = await response.json();

                activitiesContainer.innerHTML = '';
                if (activities.length === 0) {
                    activitiesContainer.innerHTML = '<p>No activities recorded for this task.</p>';
                    return;
                }

                const ul = document.createElement('ul');
                activities.forEach(act => {
                    const li = document.createElement('li');
                    li.textContent = `${act.name} (${act.status}) - ${act.duration_minutes} mins`;
                    ul.appendChild(li);
                });
                activitiesContainer.appendChild(ul);

            } catch (error) {
                console.error(`Failed to fetch activities for task ${taskId}:`, error);
                activitiesContainer.innerHTML = '<p>Failed to load activities.</p>';
            }
        }
    };

    // Initial load
    fetchHealthStatus();
    updateDashboard();

    // Refresh data every 5 minutes
    setInterval(updateDashboard, 300000);
    setInterval(fetchHealthStatus, 60000);
});