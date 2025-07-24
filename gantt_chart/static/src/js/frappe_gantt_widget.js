odoo.define('dynamic_gantt_frappe.gantt_widget', function (require) {
    'use strict';

    const AbstractAction = require('web.AbstractAction');
    const core = require('web.core');
    const { Gantt } = window;  // Frappe Gantt is loaded globally

    const FrappeGanttAction = AbstractAction.extend({
        template: 'FrappeGanttWidget',

        init: function () {
            this._super.apply(this, arguments);
            this.gantt = null;
        },

        start: function () {
            return this._super().then(() => {
                this._renderGantt();
            });
        },

        _renderGantt: function () {
            this._rpc({
                model: 'gantt.task',
                method: 'get_gantt_data',
                args: [],
            }).then((tasks) => {
                // Add validation for tasks data
                if (!tasks || !Array.isArray(tasks)) {
                    console.error('Invalid tasks data received:', tasks);
                    this._showErrorMessage('No data received from server');
                    return;
                }

                // Transform and validate tasks for Frappe Gantt
                const transformedTasks = this._transformTasksForFrappeGantt(tasks);

                if (transformedTasks.length === 0) {
                    console.error('No valid tasks found');
                    this._showErrorMessage('No valid tasks found. Please create some tasks first.');
                    return;
                }

                this._createGanttChart(transformedTasks);
            }).catch((error) => {
                console.error('Error fetching gantt data:', error);
                this._showErrorMessage('Error loading Gantt data: ' + error.message);
            });
        },

        _transformTasksForFrappeGantt: function (tasks) {
            const validTasks = [];

            tasks.forEach((task, index) => {
                // Validate task object
                if (!task || typeof task !== 'object') {
                    console.warn('Invalid task object at index', index, ':', task);
                    return;
                }

                // Validate required fields
                if (!task.name || !task.start || !task.end) {
                    console.warn('Task missing required fields (name, start, end):', task);
                    return;
                }

                // Transform task for Frappe Gantt format
                const transformedTask = {
                    id: task.id || `task_${index}`,
                    name: task.name,
                    start: task.start, // Should be in YYYY-MM-DD format
                    end: task.end,     // Should be in YYYY-MM-DD format
                    progress: Math.min(100, Math.max(0, task.progress || 0)), // Ensure 0-100 range
                    dependencies: task.dependencies || '',
                    custom_class: task.custom_class || '',
                };

                // Validate date format
                if (!this._isValidDate(transformedTask.start) || !this._isValidDate(transformedTask.end)) {
                    console.warn('Invalid date format for task:', task);
                    return;
                }

                // Ensure end date is after start date
                if (new Date(transformedTask.end) < new Date(transformedTask.start)) {
                    console.warn('End date is before start date for task:', task);
                    transformedTask.end = transformedTask.start; // Set end date same as start date
                }

                validTasks.push(transformedTask);
            });

            return validTasks;
        },

        _isValidDate: function (dateString) {
            if (!dateString) return false;
            const date = new Date(dateString);
            return date instanceof Date && !isNaN(date) && dateString.match(/^\d{4}-\d{2}-\d{2}$/);
        },

        _createGanttChart: function (tasks) {
            if (this.gantt) {
                try {
                    this.gantt.refresh(tasks);
                    return;
                } catch (error) {
                    console.error('Error refreshing Gantt chart:', error);
                    this.gantt = null; // Reset gantt instance
                }
            }

            try {
                // Clear any existing content
                const container = this.$('#gantt-chart');
                container.empty();

                this.gantt = new Gantt('#gantt-chart', tasks, {
                    header_height: 50,
                    column_width: 30,
                    step: 24,
                    view_modes: ['Quarter Day', 'Half Day', 'Day', 'Week', 'Month'],
                    bar_height: 20,
                    bar_corner_radius: 3,
                    arrow_curve: 5,
                    padding: 18,
                    view_mode: 'Day',
                    date_format: 'YYYY-MM-DD',
                    language: 'en',
                    custom_popup_html: (task) => {
                        // Add null/undefined checks
                        if (!task) {
                            console.error('Task is undefined in custom_popup_html');
                            return '<div class="details-container"><p>Invalid task data</p></div>';
                        }

                        const name = task.name || 'Unnamed Task';
                        const end = task.end || 'Not set';
                        const progress = task.progress || 0;

                        return `
                            <div class="details-container">
                                <h5>${name}</h5>
                                <p>Expected to finish by ${end}</p>
                                <p>Progress: ${progress}%</p>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${progress}%"></div>
                                </div>
                            </div>
                        `;
                    },
                    on_click: (task) => this._onTaskClick(task),
                    on_date_change: (task, start, end) => this._onDateChange(task, start, end),
                    on_progress_change: (task, progress) => this._onProgressChange(task, progress),
                    on_view_change: (mode) => console.log('View mode changed to:', mode),
                });

                console.log('Gantt chart created successfully with', tasks.length, 'tasks');
            } catch (error) {
                console.error('Error creating Gantt chart:', error);
                this._showErrorMessage('Error creating Gantt chart: ' + error.message);
            }
        },

        _showErrorMessage: function (message) {
            const container = this.$('#gantt-chart');
            container.html(`
                <div class="alert alert-warning" style="margin: 20px; padding: 20px; text-align: center;">
                    <h4>Gantt Chart Error</h4>
                    <p>${message}</p>
                    <button class="btn btn-primary" onclick="location.reload()">Reload Page</button>
                </div>
            `);
        },

        _onTaskClick: function (task) {
            if (!task || !task.id) {
                console.error('Invalid task for click event:', task);
                return;
            }

            this.do_action({
                type: 'ir.actions.act_window',
                res_model: 'gantt.task',
                res_id: parseInt(task.id),
                view_mode: 'form',
                target: 'new',
            });
        },

        _onDateChange: function (task, start, end) {
            if (!task || !task.id) {
                console.error('Invalid task for date change:', task);
                return;
            }

            const startDate = this._formatDateForOdoo(start);
            const endDate = this._formatDateForOdoo(end);

            this._rpc({
                model: 'gantt.task',
                method: 'write',
                args: [parseInt(task.id), {
                    start_date: startDate,
                    end_date: endDate
                }],
            }).then(() => {
                console.log('Task dates updated successfully');
            }).catch((error) => {
                console.error('Error updating task dates:', error);
                this._renderGantt(); // Refresh to revert changes
            });
        },

        _onProgressChange: function (task, progress) {
            if (!task || !task.id) {
                console.error('Invalid task for progress change:', task);
                return;
            }

            this._rpc({
                model: 'gantt.task',
                method: 'write',
                args: [parseInt(task.id), {
                    progress: progress
                }],
            }).then(() => {
                console.log('Task progress updated successfully');
            }).catch((error) => {
                console.error('Error updating task progress:', error);
                this._renderGantt(); // Refresh to revert changes
            });
        },

        _formatDateForOdoo: function (date) {
            if (date instanceof Date) {
                return date.toISOString().split('T')[0];
            }
            return date; // Assume it's already in YYYY-MM-DD format
        },

        destroy: function () {
            if (this.gantt) {
                this.gantt = null;
            }
            return this._super(...arguments);
        },
    });

    core.action_registry.add('gantt_chart_widget', FrappeGanttAction);

    return FrappeGanttAction;
});