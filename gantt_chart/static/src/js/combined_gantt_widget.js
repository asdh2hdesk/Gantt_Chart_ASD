odoo.define('dynamic_gantt_frappe.combined_widget', function (require) {
    'use strict';

    const AbstractAction = require('web.AbstractAction');
    const core = require('web.core');
    const FormView = require('web.FormView');
    const ListView = require('web.ListView');
    const FormController = require('web.FormController');
    const ListController = require('web.ListController');
    const { Gantt } = window;
    const QWeb = core.qweb;
    const ajax = require('web.ajax');

    const CombinedGanttAction = AbstractAction.extend({
        template: 'CombinedGanttWidget',

        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.action = action || {};
            this.gantt = null;
            this.currentTaskId = null;
            this.tasks = [];
            this.wbs_root = null;
            this.allTasks = [];
            this.project_name = 'Project Gantt Chart';
            this.availableProjects = []; // Store all available projects
        },

        start: function () {
            return this._super().then(() => {
                this._detectWBSRoot();
                this._setupLeftPanel();
                this._setupEventListeners();
                this._renderStyles();
                this._loadProjectData();
            });
        },

        _detectWBSRoot: function () {
            // Check for WBS root in action context
            if (this.action && this.action.context) {
                if (this.action.context.default_wbs_root) {
                    this.wbs_root = this.action.context.default_wbs_root;
                    console.log('Detected WBS root from context:', this.wbs_root);
                }
                if (this.action.context.project_name) {
                    this.project_name = this.action.context.project_name;
                }
            }
        },

        _loadProjectData: function () {
            // First, load all projects to populate the selector
            this._loadAllProjects().then(() => {
                // If we have a specific WBS root, load data for that project only
                if (this.wbs_root) {
                    console.log('Loading data for specific project:', this.wbs_root);
                    this._loadTasksForProject(this.wbs_root);
                } else {
                    // Load all tasks and show project selection
                    this._setupListView();
                }
            });
        },

        _loadAllProjects: function () {
            // Load all tasks to identify available projects
            return this._rpc({
                model: 'gantt.task',
                method: 'search_read',
                args: [[], ['wbs', 'name', 'start_date', 'end_date', 'lead', 'progress', 'priority', 'duration']],
            }).then((records) => {
                console.log('Raw loaded records:', records);
                this.allTasks = records;
                this.availableProjects = this._extractProjects(records);
                console.log('Extracted available projects:', this.availableProjects);

                // Filter out projects that don't have valid root tasks
                this.availableProjects = this.availableProjects.filter(project => {
                    const hasRootTask = records.some(task => task.wbs === project.wbs_root);
                    console.log(`Project ${project.wbs_root} has root task:`, hasRootTask);
                    return hasRootTask;
                });

                console.log('Final filtered projects:', this.availableProjects);
                return records;
            }).catch((error) => {
                console.error('Error loading all projects:', error);
                return [];
            });
        },

        _extractProjects: function (tasks) {
            const projectMap = new Map();

            console.log('Extracting projects from tasks:', tasks);

            tasks.forEach(task => {
                if (task.wbs) {
                    const wbsRoot = task.wbs.split('.')[0];
                    console.log(`Processing task: WBS="${task.wbs}", Root="${wbsRoot}", Name="${task.name}"`);

                    if (!projectMap.has(wbsRoot)) {
                        // Find the root task (task with WBS equal to wbsRoot)
                        const rootTask = tasks.find(t => t.wbs === wbsRoot);

                        // Only create project entry if root task exists
                        if (rootTask) {
                            console.log(`Found root task for project ${wbsRoot}:`, rootTask);
                            projectMap.set(wbsRoot, {
                                wbs_root: wbsRoot,
                                name: rootTask.name,
                                task_count: 0,
                                start_date: null,
                                end_date: null,
                                root_task_id: rootTask.id
                            });
                        } else {
                            console.log(`No root task found for WBS root "${wbsRoot}" - skipping`);
                            return; // Skip this task if no root task exists
                        }
                    }

                    const project = projectMap.get(wbsRoot);
                    if (project) {
                        project.task_count++;

                        // Update date range
                        if (task.start_date) {
                            if (!project.start_date || task.start_date < project.start_date) {
                                project.start_date = task.start_date;
                            }
                        }
                        if (task.end_date) {
                            if (!project.end_date || task.end_date > project.end_date) {
                                project.end_date = task.end_date;
                            }
                        }
                    }
                }
            });

            const result = Array.from(projectMap.values()).sort((a, b) => {
                // Sort numerically if both are numbers, otherwise alphabetically
                const aNum = parseInt(a.wbs_root);
                const bNum = parseInt(b.wbs_root);
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return aNum - bNum;
                }
                return a.wbs_root.localeCompare(b.wbs_root);
            });

            console.log('Final extracted projects:', result);
            return result;
        },

        _loadTasksForProject: function (wbsRoot) {
            // Load tasks specifically for this project
            this._rpc({
                model: 'gantt.task',
                method: 'get_gantt_data_for_project',
                args: [wbsRoot],
            }).then((tasks) => {
                console.log('Loaded tasks for project', wbsRoot, ':', tasks);
                this.allTasks = tasks;
                this.tasks = tasks;
                this._renderTaskList(tasks);
                this._renderGanttWithFilteredTasks();
            }).catch((error) => {
                console.error('Error loading project tasks:', error);
                this._showGanttError('Error loading project data: ' + error.message);
            });
        },

        _setupLeftPanel: function () {
            const context = this.action && this.action.context ? this.action.context : {};

            // If we have a specific project, don't show the general list view
            if (!this.wbs_root) {
                this._setupListView(context);
            }
        },

        _renderWbsTable: function () {
            const tbody = this.$('.gantt-left-table tbody');
            if (tbody.length === 0) {
                console.log('WBS table not found in template');
                return;
            }

            tbody.empty();

            this.allTasks.forEach(task => {
                const row = $(`
                    <tr class="wbs-row" data-wbs="${task.wbs}">
                        <td>${task.wbs}</td>
                        <td>${task.name}</td>
                        <td>${task.duration || 'N/A'}</td>
                    </tr>
                `);
                tbody.append(row);
            });

            // Attach click handler to each row
            this.$('.wbs-row').on('click', (ev) => {
                const wbsCode = $(ev.currentTarget).data('wbs');
                console.log("WBS Clicked:", wbsCode);
                this.wbs_root = wbsCode;
                this._renderGanttWithFilteredTasks();
            });
        },

        _setupListView: function () {
            const listContainer = this.$('.left-panel .list-container');

            const context = this.action && this.action.context ? this.action.context : {};
            const projectId = context.default_project_id;

            if (projectId) {
                this.tasks = this.tasks.filter(task => task.project_id[0] === projectId);
            }

            this._rpc({
                model: 'gantt.task',
                method: 'search_read',
                args: [[], ['wbs', 'name', 'start_date', 'end_date', 'lead', 'progress', 'priority', 'duration']],
            }).then((records) => {
                console.log('Fetched tasks:', records);
                this.tasks = records;
                this.allTasks = records;
                this._renderTaskList(records);

                // Initialize Gantt with first project if no specific root is set
                if (!this.wbs_root && records.length > 0) {
                    const groupedTasks = this._groupTasksByWBS(records);
                    const wbsRoots = Object.keys(groupedTasks).sort();
                    if (wbsRoots.length > 0) {
                        this.wbs_root = wbsRoots[0];
                        console.log('Setting default wbs_root to:', this.wbs_root);
                    }
                }

                this._renderGanttWithFilteredTasks();
            }).catch((error) => {
                console.error('Error fetching tasks:', error);
            });
        },

        _renderTaskList: function (records) {
            const listContainer = this.$('.left-panel .list-container');

            // If we're in project-specific mode, show simplified task list
            if (this.wbs_root && this.action.context && this.action.context.default_wbs_root) {
                this._renderProjectTaskTable(records);
                return;
            }

            // Otherwise show grouped task list in table format
            const groupedTasks = this._groupTasksByWBS(records);
            let listHtml = `
                <div class="task-list">
                    <div class="task-list-header">
                        <h4>Tasks</h4>
                        <button class="btn btn-sm btn-primary create-task-btn">
                            <i class="fa fa-plus"></i> New Task
                        </button>
                    </div>
                    <div class="task-table-container">
            `;

            const wbsRoots = Object.keys(groupedTasks).sort();
            wbsRoots.forEach(wbsRoot => {
                const isSelected = this.wbs_root === wbsRoot;
                listHtml += `
                    <div class="project-group ${isSelected ? 'selected-project' : ''}" data-wbs-root="${wbsRoot}">
                        <h5 class="project-title" data-wbs-root="${wbsRoot}">
                            <i class="fa fa-caret-${isSelected ? 'down' : 'right'} project-caret"></i>
                            Project ${wbsRoot}
                            <button class="btn btn-xs btn-info project-details-btn" data-wbs-root="${wbsRoot}" title="Project Details">
                                <i class="fa fa-info-circle"></i>
                            </button>
                        </h5>
                        <div class="project-tasks" style="display: ${isSelected ? 'block' : 'none'};">
                            <table class="task-table">
                                <thead>
                                    <tr>
                                        <th>WBS</th>
                                        <th>TASK</th>
                                        <th>START</th>
                                        <th>END</th>
                                        <th>ASSIGNEE</th>
                                        <th>DURATION</th>
                                        <th>PROGRESS</th>
                                    </tr>
                                </thead>
                                <tbody>
                `;

                groupedTasks[wbsRoot].sort((a, b) => a.wbs.localeCompare(b.wbs)).forEach(record => {
                    listHtml += this._renderTaskTableRow(record);
                });

                listHtml += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            });

            listHtml += `
                    </div>
                </div>
            `;

            listContainer.html(listHtml);
        },

        _renderProjectTaskTable: function (records) {
            const listContainer = this.$('.left-panel .list-container');

            let listHtml = `
                <div class="task-list">
                    <div class="task-list-header">
                        <h4>${this.project_name}</h4>
                        <div class="project-actions">
                            <button class="btn btn-sm btn-success project-selector-btn" title="Switch Project">
                                <i class="fa fa-exchange"></i>
                            </button>
                            <button class="btn btn-sm btn-info project-details-btn"
                                    data-wbs-root="${this.wbs_root}"
                                    title="Project Details">
                                Edit
                            </button>
                            <button class="btn btn-sm btn-primary export-btn" data-wbs-root="${this.wbs_root}" title="Export Project">
                                Export
                            </button>
                        </div>
                    </div>
                    <div class="task-table-container project-specific-tasks">
                        <table class="task-table">
                            <thead>
                                <tr>
                                    <th>S. no.</th>
                                    <th>Task</th>
                                    <th>Start</th>
                                    <th>End</th>
                                    <th>Assignee</th>
                                    <th>Duration</th>
                                    <th>Progress</th>
                                </tr>
                            </thead>
                            <tbody>
            `;

            // Sort tasks by WBS
            records.sort((a, b) => a.wbs.localeCompare(b.wbs)).forEach(record => {
                listHtml += this._renderTaskTableRow(record);
            });

            listHtml += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;

            listContainer.html(listHtml);
        },

        _showProjectSelector: function () {
            const modalHtml = `
                <div class="project-selector-modal" style="
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.5);
                    z-index: 9999;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                ">
                    <div class="project-selector-content" style="
                        background: white;
                        border-radius: 8px;
                        padding: 20px;
                        max-width: 600px;
                        width: 90%;
                        max-height: 80%;
                        overflow-y: auto;
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                    ">
                        <div class="modal-header" style="
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            margin-bottom: 20px;
                            padding-bottom: 10px;
                            border-bottom: 1px solid #dee2e6;
                        ">
                            <h4 style="margin: 0; color: #333;">Select Project</h4>
                            <button class="close-modal-btn" style="
                                background: none;
                                border: none;
                                font-size: 24px;
                                cursor: pointer;
                                color: #999;
                            ">&times;</button>
                        </div>
                        <div class="projects-list">
                            ${this._renderProjectsList()}
                        </div>
                    </div>
                </div>
            `;

            // Remove existing modal if any
            $('.project-selector-modal').remove();

            // Add modal to body
            $('body').append(modalHtml);

            // Event handlers
            $('.close-modal-btn, .project-selector-modal').on('click', (e) => {
                if (e.target === e.currentTarget) {
                    $('.project-selector-modal').remove();
                }
            });

            $('.project-item').on('click', (e) => {
                const wbsRoot = $(e.currentTarget).data('wbs-root');
                this._switchToProject(wbsRoot);
                $('.project-selector-modal').remove();
            });
        },

        _renderProjectsList: function () {
            let projectsHtml = '';

            this.availableProjects.forEach(project => {
                const isCurrentProject = project.wbs_root === this.wbs_root;
                projectsHtml += `
                    <div class="project-item ${isCurrentProject ? 'current-project' : ''}"
                         data-wbs-root="${project.wbs_root}"
                         style="
                            padding: 15px;
                            margin-bottom: 10px;
                            border: 1px solid #dee2e6;
                            border-radius: 4px;
                            cursor: pointer;
                            transition: all 0.2s ease;
                            ${isCurrentProject ? 'background-color: #e3f2fd; border-color: #2196f3;' : 'background-color: #f8f9fa;'}
                         "
                         onmouseover="this.style.backgroundColor='#e9ecef'"
                         onmouseout="this.style.backgroundColor='${isCurrentProject ? '#e3f2fd' : '#f8f9fa'}'"
                    >
                        <div class="project-header" style="display: flex; justify-content: space-between; align-items: center;">
                            <h5 style="margin: 0; color: #333;">
                                ${isCurrentProject ? '<i class="fa fa-check-circle" style="color: #4caf50; margin-right: 8px;"></i>' : ''}
                                Project ${project.wbs_root}: ${project.name}
                            </h5>
                            <span class="badge badge-info">${project.task_count} tasks</span>
                        </div>
                        <div class="project-details" style="margin-top: 8px; color: #666; font-size: 0.9em;">
                            <div>
                                <i class="fa fa-calendar" style="margin-right: 5px;"></i>
                                ${project.start_date ? this._formatDate(project.start_date) : 'No start date'} -
                                ${project.end_date ? this._formatDate(project.end_date) : 'No end date'}
                            </div>
                        </div>
                    </div>
                `;
            });

            return projectsHtml;
        },

        _switchToProject: function (wbsRoot) {
            console.log('Switching to project:', wbsRoot);

            // Update current project
            this.wbs_root = wbsRoot;

            // Find project name
            const project = this.availableProjects.find(p => p.wbs_root === wbsRoot);
            this.project_name = project ? `Project: ${project.name}` : `Project: ${wbsRoot}`;

            // Load tasks for the new project
            this._loadTasksForProject(wbsRoot);
        },

        _renderTaskTableRow: function (record) {
            const indentLevel = (record.wbs.split('.').length - 1) * 15;
            const startDate = this._formatDate(record.start_date);
            const endDate = this._formatDate(record.end_date);
            const assignee = record.lead && Array.isArray(record.lead) && record.lead.length > 1 ? record.lead[1] : 'Unassigned';
            const duration = record.duration || 'N/A';
            const progress = record.progress || 0;

            return `
                <tr class="task-row" data-task-id="${record.id}">
                    <td class="wbs-cell">
                        ${record.wbs}
                    </td>
                    <td class="name-cell">
                        ${record.name}
                    </td>
                    <td class="start-cell">
                        ${startDate}
                    </td>
                    <td class="end-cell">
                        ${endDate}
                    </td>
                    <td class="lead-cell">
                        ${assignee}
                    </td>
                    <td class="duration-cell">
                        ${duration}
                    </td>
                    <td class="progress-cell">
                        ${progress}%
                    </td>
                </tr>
            `;
        },

        _expandProject: function(wbsRoot) {
            console.log('Expanding project:', wbsRoot);

            // Remove selected class from all projects
            this.$('.project-group').removeClass('selected-project');

            // Collapse all projects first
            this.$('.project-tasks').slideUp(300);
            this.$('.project-caret').removeClass('fa-caret-down').addClass('fa-caret-right');

            // Expand the selected project
            const $targetGroup = this.$('.project-group[data-wbs-root="' + wbsRoot + '"]');
            const $targetTasks = $targetGroup.find('.project-tasks');
            const $targetCaret = $targetGroup.find('.project-caret');

            $targetGroup.addClass('selected-project');
            $targetTasks.slideDown(300);
            $targetCaret.removeClass('fa-caret-right').addClass('fa-caret-down');

            // Update current WBS root
            this.wbs_root = wbsRoot;
            console.log('WBS root updated to:', this.wbs_root);
        },

        _openProjectDetails: function(wbsRoot) {
            console.log('Opening project details for WBS root:', wbsRoot);

            this.do_action({
                type: 'ir.actions.act_window',
                name: `Project Details - ${wbsRoot}`,
                res_model: 'project.details.wizard',
                view_mode: 'form',
                target: 'new',
                context: {
                    default_wbs_root: wbsRoot,
                },
            });
        },

        _groupTasksByWBS: function (records) {
            const grouped = {};
            records.forEach(record => {
                const wbsRoot = record.wbs ? record.wbs.split('.')[0] : '0';
                if (!grouped[wbsRoot]) {
                    grouped[wbsRoot] = [];
                }
                grouped[wbsRoot].push(record);
            });
            return grouped;
        },

        _getPriorityClass: function (priority) {
            const priorityClasses = {
                'low': 'priority-low',
                'medium': 'priority-medium',
                'high': 'priority-high',
                'urgent': 'priority-urgent'
            };
            return priorityClasses[priority] || 'priority-medium';
        },

        _getProgressBar: function (progress) {
            const progressValue = progress || 0;
            return `
                <div class="progress-container">
                    <div class="progress">
                        <div class="progress-bar" style="width: ${progressValue}%"></div>
                    </div>
                    <span class="progress-text">${progressValue}%</span>
                </div>
            `;
        },

        _formatDate: function (dateString) {
            if (!dateString) return 'Not set';
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                month: 'numeric',
                day: 'numeric',
                year: 'numeric'
            });
        },

        _renderStyles: function () {
            const style = `
                <style>
                    .combined-gantt-container {
                        display: flex;
                        height: 100vh;
                        background-color: #f8f9fa;
                        width: 100%;
                        box-sizing: border-box;
                        overflow-y: auto; /* Single unified vertical scroll */
                        scrollbar-width: none;
                        -ms-overflow-style: none;
                    }

                    .combined-gantt-container::-webkit-scrollbar {
                        display: none;
                    }

                    .left-panel {
                        position: relative;
                        margin-left: -10px;
                        margin-top: -8px;

                        min-width: 35%;
                        flex: 0 0 35%;
                        max-width: 35%;
                        border-right: 1px solid #dee2e6;
                        background-color: white;
                        box-sizing: border-box;
                        display: flex;
                        flex-direction: column;
                        overflow: hidden; /* Remove individual scrolling */
                        overflow-y: visible; /* Allow scrolling but hide scrollbar */
                        scrollbar-width: none; /* Firefox */
                        -ms-overflow-style: none; /* IE/Edge */
                    }
                    .left-panel::-webkit-scrollbar {
                        display: none; /* Chrome, Safari, Opera */
                    }

                    .right-panel {
                        position: relative;
                        width: 65%;
                        flex: 1;
                        min-width: 65%;
                        max-width: 65%;
                        display: flex;
                        flex-direction: column;
                        overflow-x: auto; /* Keep horizontal scroll for Gantt */
//                        overflow-y: visible; /* Remove vertical scrolling */
                        box-sizing: border-box;
                        scrollbar-width: none;

                    }
                    .right-panel::-webkit-scrollbar {
                        display: none;
                    }

                    .gantt-header {
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        padding: 10px 10px;
                        background-color: white;
                        border-bottom: 1px solid #dee2e6;
                    }

                    .gantt-container {
                        flex: 1;
                        padding: 0;
                        overflow-x: auto; /* Independent horizontal scrolling */
                        overflow-y: visible; /* No vertical scrolling */
                        background-color: #fff;
                        scrollbar-width: none;
                        -ms-overflow-style: none;
                    }
                    .gantt-container::-webkit-scrollbar {
                        display: none;
                    }
                    .gantt-title{
                        font-family: "Monotype Corsiva", cursive, sans-serif;
                        font-size: 200px;
                        font-weight: 600;
                        color: #343a40;

                    }
    //                .gantt-container::-webkit-scrollbar {
    //                    height: 8px;
    //                }
    //
    //                .gantt-container::-webkit-scrollbar-track {
    //                    background: #f1f1f1;
    //                }
    //
    //                .gantt-container::-webkit-scrollbar-thumb {
    //                    background: #c1c1c1;
    //                    border-radius: 4px;
    //                }
    //
    //                .gantt-container::-webkit-scrollbar-thumb:hover {
    //                    background: #a8a8a8;
    //                }

                    .task-list-header {
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        padding: 10px 10px;
                        background-color: white;
                        border-bottom: 1px solid #dee2e6;
                    }

                    .project-actions {
                        display: flex;
                        gap: 5px;
                    }

                    .project-specific-tasks {
                        border-left: none;
                        padding-top: 8px;
                        background-color: transparent;
                    }

//                    .project-title {
//                        font-size: 1.1em;
//                        color: #333;
//                        background-color: #f8f9fa;
//                        padding-top: 100px;
//                        margin: 0;
//                        user-select: none;
//                        transition: background-color 0.3s ease;
//                        display: flex;
//                        justify-content: space-between;
//                        align-items: center;
//                    }

    //                .project-title:hover {
    //                    background-color: #e9ecef;
    //                }

//                    .selected-project .project-title {
//                        background-color: #d4edda;
//                        font-weight: bold;
//                    }

                    .project-caret {
                        transition: transform 0.3s ease;
                    }

                    .project-details-btn {
                        margin-left: auto;
                        margin-right: 10px;
                    }

                    .project-tasks {
//                        padding-left: 10px;
                        transition: all 0.3s ease;
                        overflow: visible;
                    }

                    .task-table-container {
                        overflow: visible; /* No scrolling */
                    }

                    .task-table {
                        width: 100%;
                        background-color: white;

                    }

                    .task-table thead {
                        background-color: #f8f9fa;
                        border-bottom: 1px solid #dee2e6;
    //                    overflow-x: flex;
                    }

                    .task-table th {
                        text-align: left;
                        font-weight: 600;
                        color: #495057;
                        border-right: 1px solid #dee2e6;
                        font-size: 0.9em;
                        height: 37px;
    //                    padding: 10px 8px;
                    }

                    .task-table tbody tr {
                        border-bottom: 1px solid #dee2e6;
                        transition: background-color 0.2s ease;
                        height: 37px;
                        background-color: #fff;
                    }

                    .task-table tbody tr:hover {
                        background-color: #f8f9fa;
                    }

                    .task-table tbody tr:last-child {
                        border-bottom: none;
                    }

                    .task-table td {
                        padding: 8px;
                        color: #495057;
                        border-right: 1px solid #dee2e6;
                        font-size: 0.9em;
                        height: 37px;
                        white-space: nowrap;
                    }

                    .task-row {
                        cursor: pointer;
                    }

                    .task-row.selected {
                        background-color: #e3f2fd !important;
                    }

                    .gantt-controls {
                        display: flex;
                        gap: 15px;
                        align-items: center;
                    }

                    .view-mode-controls {
                        display: flex;
                        gap: 5px;
                    }

                    .view-mode-btn.active {
                        background-color: #007bff;
                        color: white;
                        border-color: #007bff;
                    }

                    #gantt-chart {
                        min-height: 400px;
                        width: 100%;
                    }
                    .scrollable-hidden {
                        overflow-y: auto;
                        scrollbar-width: none;
                        -ms-overflow-style: none;
                    }

                    .scrollable-hidden::-webkit-scrollbar {
                        display: none;

                    }
                    .task-list {
                        overflow: visible;
    //                    overflow-y: auto;
                        scrollbar-width: none;
                        -ms-overflow-style: none;
                    }

                    /* Project Selector Button */
                    .project-selector-btn {
                        transition: all 0.2s ease;
                    }

                    .project-selector-btn:hover {
                        background-color: #28a745 !important;
                        border-color: #28a745 !important;
                    }

                    /* Project Selector Modal Styles */
                    .project-item:hover {
                        transform: translateY(-1px);
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    }

                    .current-project {
                        position: relative;
                    }

                    .current-project::before {
                        content: '';
                        position: absolute;
                        left: 0;
                        top: 0;
                        bottom: 0;
                        width: 4px;
                        background-color: #2196f3;
                        border-radius: 0 4px 4px 0;
                    }

                </style>
            `;
            this.$el.append(style);
        },

        _setupEventListeners: function () {
            // Remove any existing event handlers to prevent duplicates
            this.$('.left-panel').off();
            this.$('.gantt-header').on('click', '.view-mode-btn', (e) => {
                const viewMode = $(e.currentTarget).data('view-mode');
                this._changeViewMode(viewMode);
            });

            // Project selector button click events
            this.$('.left-panel').on('click', '.project-selector-btn', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this._showProjectSelector();
            });

            // Project details button click events
            this.$('.left-panel').on('click', '.project-details-btn', (e) => {
                e.preventDefault();
                e.stopPropagation();

                const wbsRoot = $(e.currentTarget).data('wbs-root');
                console.log('Clicked project details for:', wbsRoot);

                if (!wbsRoot) {
                    console.error('No WBS root found for project details button');
                    return;
                }

                // Call the model method
                this._rpc({
                    model: 'gantt.task',
                    method: 'open_project_detail',
                    args: [ ],
                }).then((action) => {
                    if (action) {
                        this.do_action(action);
                    }
                }).catch((error) => {
                    console.error('Error opening project details:', error);
                });
            });

            this.$('.left-panel').on('click', '.export-btn', (e) => {
                e.preventDefault();
                const wbsRoot = $(e.currentTarget).data('wbs-root');
                this._exportProjectTasks(wbsRoot);
            });
            // Project title click events - Only if not in project-specific mode
            if (!this.action.context || !this.action.context.default_wbs_root) {
                this.$('.left-panel').on('click', '.project-title', (e) => {
                    // Check if the click was on the details button
                    if ($(e.target).closest('.project-details-btn').length > 0) {
                        return; // Let the details button handle this
                    }

                    e.preventDefault();
                    e.stopPropagation();

                    const wbsRoot = $(e.currentTarget).data('wbs-root');
                    console.log('Clicked project:', wbsRoot);

                    if (!wbsRoot) {
                        console.error('No WBS root found for clicked project');
                        return;
                    }

                    // Always expand the clicked project and update Gantt
                    this._expandProject(wbsRoot);
                    this._renderGanttWithFilteredTasks();
                });
            }

            // Create task button click events
            this.$('.left-panel').on('click', '.create-task-btn', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this._createTask();
            });

            // Task row click events
            this.$('.left-panel').on('click', '.task-row', (e) => {
                const taskId = $(e.currentTarget).data('task-id');
                console.log('Clicked task:', taskId);

                if (taskId) {
                    this._highlightTask(taskId);
                    this._editTask(taskId);
                }
            });

            this.$('.left-panel').on('click', '.task-row', (e) => {
                const taskId = $(e.currentTarget).data('task-id');
                console.log('Clicked task:', taskId);

                if (taskId) {
                    this._highlightTask(taskId);
                    this._editTask(taskId);
                }
            });

            // Synchronize vertical scroll between left panel and Gantt chart
            const leftPanelEl = this.$('.left-panel')[0];
            const ganttContainerEl = this.$('.gantt-container')[0];

            if (leftPanelEl && ganttContainerEl) {
                leftPanelEl.addEventListener("scroll", () => {
                    ganttContainerEl.scrollTop = leftPanelEl.scrollTop;
                });

                ganttContainerEl.addEventListener("scroll", () => {
                    leftPanelEl.scrollTop = ganttContainerEl.scrollTop;
                });
            }

        },

        _highlightTask: function (taskId) {
            this.$('.task-row').removeClass('selected');
            this.$('.left-panel .task-row[data-task-id="' + taskId + '"]').addClass('selected');

            // Highlight in gantt (if gantt is rendered)
            if (this.gantt) {
                console.log('Highlighting task in gantt:', taskId);
            }
        },

        _editTask: function (taskId) {
            this.do_action('gantt_chart.action_gantt_task_window', {
                additional_context: {},
                flags: { mode: 'form' },
                res_id: taskId,
            });
        },

        _deleteTask: function (taskId) {
            if (confirm('Are you sure you want to delete this task?')) {
                this._rpc({
                    model: 'gantt.task',
                    method: 'unlink',
                    args: [taskId],
                }).then(() => {
                    this._refreshData();
                }).catch((error) => {
                    alert('Error deleting task: ' + error.message);
                });
            }
        },

        _createTask: function () {
            const context = {
                default_name: 'New Task',
                default_wbs: this.wbs_root || '1',
            };

            // If we're in project-specific mode, set the WBS prefix
            if (this.wbs_root) {
                // Find the next available WBS number for this project
                const projectTasks = this.allTasks.filter(task =>
                    task.wbs && task.wbs.startsWith(this.wbs_root + '.')
                );

                let nextSubTask = 1;
                if (projectTasks.length > 0) {
                    const subTaskNumbers = projectTasks.map(task => {
                        const parts = task.wbs.split('.');
                        return parts.length > 1 ? parseInt(parts[1]) || 0 : 0;
                    });
                    nextSubTask = Math.max(...subTaskNumbers) + 1;
                }

                context.default_wbs = `${this.wbs_root}.${nextSubTask}`;
            }

            this.do_action('gantt_chart.action_gantt_task_window', {
                additional_context: context,
            });
        },

        _refreshData: function () {
            if (this.wbs_root && this.action.context && this.action.context.default_wbs_root) {
                // Refresh data for specific project
                this._loadTasksForProject(this.wbs_root);
            } else {
                // Refresh all data
                this._setupListView();
            }
        },

        _changeViewMode: function (viewMode) {
            if (this.gantt) {
                this.gantt.change_view_mode(viewMode);

                // Update active button
                this.$('.view-mode-btn').removeClass('active');
                this.$('.view-mode-btn[data-view-mode="' + viewMode + '"]').addClass('active');
            }
        },

        _renderGanttWithFilteredTasks: function () {
            console.log('Filtering tasks for wbs_root:', this.wbs_root);

            if (!this.wbs_root || !this.allTasks || this.allTasks.length === 0) {
                console.log('No WBS root set or no tasks available');
                this._showGanttError('Please select a project from the left panel.');
                return;
            }

            console.log('All tasks before filtering:', this.allTasks);
            console.log('Looking for tasks with WBS starting with:', this.wbs_root);

            // Filter tasks that belong to the selected project
            const filteredTasks = this.allTasks.filter(task => {
                if (!task.wbs) {
                    console.log('Task without WBS:', task);
                    return false;
                }

                // Convert both to strings for comparison
                const taskWbs = String(task.wbs);
                const rootWbs = String(this.wbs_root);

                // Include exact match and sub-tasks
                const isExactMatch = taskWbs === rootWbs;
                const isSubTask = taskWbs.startsWith(rootWbs + '.');
                const belongs = isExactMatch || isSubTask;

                console.log(`Task WBS: "${taskWbs}", Root: "${rootWbs}", Exact: ${isExactMatch}, Sub: ${isSubTask}, Belongs: ${belongs}`);

                if (belongs) {
                    console.log('Including task:', task.wbs, task.name);
                }
                return belongs;
            });

            console.log('Filtered tasks for project', this.wbs_root + ':', filteredTasks);

            if (filteredTasks.length === 0) {
                // Show more detailed debug info
                console.log('Available WBS codes in all tasks:');
                this.allTasks.forEach(task => {
                    console.log(`- Task ID: ${task.id}, WBS: "${task.wbs}", Name: ${task.name}`);
                });
                this._showGanttError(`No tasks found for project ${this.wbs_root}. Check console for debug info.`);
                return;
            }

            const transformedTasks = this._transformTasksForFrappeGantt(filteredTasks);
            console.log('Transformed tasks:', transformedTasks);

            if (transformedTasks.length === 0) {
                this._showGanttError(`No valid tasks found for project ${this.wbs_root}. Tasks may have invalid dates.`);
                return;
            }

            this._createGanttChart(transformedTasks);
        },

        _transformTasksForFrappeGantt: function (tasks) {
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            const todayStr = today.toISOString().split('T')[0];
            const transformedTasks = [];

            tasks.forEach((task) => {
                const wbsParts = task.wbs ? task.wbs.split('.') : [];
                let dependencies = [];

                if (wbsParts.length > 1) {
                    const parentWbs = wbsParts.slice(0, -1).join('.');
                    const parentTask = tasks.find(t => t.wbs === parentWbs);
                    if (parentTask) {
                        dependencies = [parentTask.id.toString()];
                    }
                }

                const start = task.start_date || task.start;
                const end = task.end_date || task.end;

                if (!this._isValidDate(start) || !this._isValidDate(end)) {
                    console.log('Invalid dates for task:', task.name, start, end);
                    return;
                }

                const taskEndDate = new Date(end);
                taskEndDate.setHours(0, 0, 0, 0);
                const isDelayed = task.progress < 100 && taskEndDate.getTime() < today.getTime();

                // Main task bar
                transformedTasks.push({
                    id: task.id.toString(),
                    name: `${task.wbs}: ${task.name}`,
                    start: start,
                    end: end,
                    progress: task.progress || 0,
                    dependencies: dependencies,
                    custom_class: `wbs-group-${wbsParts[0]} priority-${task.priority || 'medium'}`
                });
            });

            return transformedTasks;
        },

        _isValidDate: function (dateString) {
            if (!dateString) return false;
            const date = new Date(dateString);
            return date instanceof Date && !isNaN(date) && dateString.match(/^\d{4}-\d{2}-\d{2}$/);
        },

        _createGanttChart: function (tasks) {
            console.log("Creating Gantt chart with tasks:", tasks);

            if (this.gantt) {
                try {
                    this.gantt.refresh(tasks);
                    return;
                } catch (error) {
                    console.error('Error refreshing Gantt chart:', error);
                    this.gantt = null;
                }
            }

            try {
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
                        if (!task) {
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
                });

                console.log('Gantt chart created successfully with', tasks.length, 'tasks for project', this.wbs_root);
            } catch (error) {
                console.error('Error creating Gantt chart:', error);
                this._showGanttError('Error creating Gantt chart: ' + error.message);
            }
        },

        _showGanttError: function (message) {
            const container = this.$('#gantt-chart');
            container.html(`
                <div class="alert alert-warning" style="margin: 20px; padding: 20px; text-align: center;">
                    <h4>Gantt Chart</h4>
                    <p>${message}</p>
                    <button class="btn btn-primary refresh-btn">Reload Data</button>
                </div>
            `);
        },

        _onTaskClick: function (task) {
            if (!task || !task.id) {
                console.error('Invalid task for click event:', task);
                return;
            }

            // Highlight in left panel
            this._highlightTask(parseInt(task.id));

            // Edit task
            this._editTask(parseInt(task.id));
            // Refresh data after a delay
            setTimeout(() => this._refreshData(), 2000);
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
                args: [parseInt(task.id), { start_date: startDate, end_date: endDate }],
            }).then(() => {
                console.log('Task dates updated successfully');
                this._refreshData();
            }).catch((error) => {
                console.error('Error updating task dates:', error);
                this._renderGanttWithFilteredTasks();
            });
        },

        _onProgressChange: function (task, progress) {
            if (!task || !task.id) {
                console.error('Invalid task for progress change:', task);
                return;
            }
            console.log('Updating progress for task', task.id, 'to', progress);

            this._rpc({
                model: 'gantt.task',
                method: 'write',
                args: [parseInt(task.id), { progress: progress }],
            }).then(() => {
                console.log('Task progress updated successfully');
                this._refreshData();
            }).catch((error) => {
                console.error('Error updating task progress:', error);
                this._renderGanttWithFilteredTasks();
            });
        },

        _formatDateForOdoo: function (date) {
            if (date instanceof Date) {
                return date.toISOString().split('T')[0];
            }
            return date;
        },

        _exportProjectTasks: function (wbsRoot) {
            console.log('Creating manual Gantt chart for:', wbsRoot);

            const tasks = this.allTasks.filter(task => {
                return task.wbs === wbsRoot || task.wbs.startsWith(wbsRoot + '.');
            });

            if (!tasks.length) {
                alert(`No tasks found for project "${wbsRoot}".`);
                return;
            }

            // Calculate project date range
            const calculateProjectDates = () => {
                let projectStart = null;
                let projectEnd = null;

                tasks.forEach(task => {
                    if (task.start_date) {
                        const startDate = new Date(task.start_date);
                        if (!projectStart || startDate < projectStart) projectStart = startDate;
                    }
                    if (task.end_date) {
                        const endDate = new Date(task.end_date);
                        if (!projectEnd || endDate > projectEnd) projectEnd = endDate;
                    }
                });

                if (!projectStart) projectStart = new Date();
                if (!projectEnd) {
                    projectEnd = new Date(projectStart);
                    projectEnd.setMonth(projectEnd.getMonth() + 3); // 3 months default
                }

                return { projectStart, projectEnd };
            };

            // Generate date columns for Gantt timeline
            const generateDateColumns = (startDate, endDate) => {
                const dates = [];
                const current = new Date(startDate);
                while (current <= endDate) {
                    dates.push(new Date(current));
                    current.setDate(current.getDate() + 1);
                }
                return dates;
            };

            // Check if a date falls within task duration
            const isDateInTask = (date, taskStart, taskEnd) => {
                if (!taskStart || !taskEnd) return false;
                const start = new Date(taskStart);
                const end = new Date(taskEnd);
                return date >= start && date <= end;
            };

            // Format date for display
            const formatDate = (date) => {
                const day = date.getDate().toString().padStart(2, '0');
                const month = (date.getMonth() + 1).toString().padStart(2, '0');
                return `${day}/${month}`;
            };

            // Create the Excel with colored Gantt chart
            const createGanttExcel = async () => {
                try {
                    if (typeof ExcelJS === 'undefined') {
                        const loadExcelJS = this._loadExcelJS || function() {
                            return new Promise((resolve, reject) => {
                                const script = document.createElement('script');
                                script.src = 'https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.3.0/exceljs.min.js';
                                script.onload = () => resolve();
                                script.onerror = () => reject(new Error('Failed to load ExcelJS'));
                                document.head.appendChild(script);
                            });
                        };
                        await loadExcelJS();
                    }

                    const { projectStart, projectEnd } = calculateProjectDates();
                    const dateColumns = generateDateColumns(projectStart, projectEnd);

                    const workbook = new ExcelJS.Workbook();
                    const sheet = workbook.addWorksheet('Project Gantt Chart');

                    // Simple header row
                    const headers = ['Project Name', 'Start Date', 'End Date', 'WBS', 'Task', 'Lead', 'Start', 'End', 'Days', '% Done', 'Duration', ''];
                    dateColumns.forEach(date => headers.push(formatDate(date)));
                    const headerRow = sheet.addRow(headers);
                    headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
                    headerRow.fill = {
                        type: 'pattern',
                        pattern: 'solid',
                        fgColor: { argb: 'FF4A90E2' } // Blue background
                    };

                    // Set column widths
                    const widths = [15, 12, 12, 8, 25, 15, 12, 12, 8, 10, 10, 2].concat(dateColumns.map(() => 3));
                    widths.forEach((w, i) => sheet.getColumn(i + 1).width = w);

                    // Freeze the header row
                    sheet.views = [{ state: 'frozen', xSplit: 0, ySplit: 1, activeCell: 'A2' }];

                    // Task rows with colored Gantt cells and gaps
                    tasks.forEach((task, index) => {
                        const rowValues = [
                            `Project ${wbsRoot}`, // Project Name
                            task.start_date || projectStart.toLocaleDateString(), // Start Date
                            task.end_date || projectEnd.toLocaleDateString(), // End Date
                            task.wbs,
                            task.name,
                            task.lead ? task.lead[1] : '',
                            task.start_date || '',
                            task.end_date || '',
                            task.duration || '',
                            (task.progress || 0) + '%',
                            task.duration || '',
                            ''
                        ];

                        // Push blanks for each Gantt date
                        dateColumns.forEach(() => rowValues.push(''));
                        const row = sheet.addRow(rowValues);
                        row.height = 20; // Base height for task row

                        // Fill colors for each task duration
                        dateColumns.forEach((date, idx) => {
                            if (isDateInTask(date, task.start_date, task.end_date)) {
                                const cell = row.getCell(13 + idx); // First date column is 13th (after 12 headers)
                                cell.fill = {
                                    type: 'pattern',
                                    pattern: 'solid',
                                    fgColor: { argb: 'FF77A651' } // Consistent green fill
                                };
                            }
                        });

                        // Add an empty row for gap (except after the last task)
                        if (index < tasks.length - 1) {
                            const emptyRow = sheet.addRow([]);
                            emptyRow.height = 5; // Small gap height
                        }
                    });

                    // Save Excel
                    const buffer = await workbook.xlsx.writeBuffer();
                    saveAs(new Blob([buffer]), `Project_${wbsRoot}_GanttChart.xlsx`);

                    alert(`Gantt chart exported successfully!\n\nProject: ${wbsRoot}\nDate range: ${projectStart.toLocaleDateString()} to ${projectEnd.toLocaleDateString()}\nTotal days: ${dateColumns.length}\nTasks: ${tasks.length}`);

                } catch (error) {
                    console.error('Error creating Gantt Excel:', error);
                    alert('Error creating Gantt chart: ' + error.message);
                }
            };

            // Execute the export
            createGanttExcel();
        },


        destroy: function () {
            if (this.gantt) {
                this.gantt = null;
            }
            return this._super(...arguments);
        },
    });

    core.action_registry.add('combined_gantt_widget', CombinedGanttAction);
    return CombinedGanttAction;
});