import { truncate } from '../../shared/utils.js';

/** Plain-text summaries; HTML escaping happens in wrapToolUse / finishToolResult. */
export function getToolSummary(name, inp) {
    if (name === 'Bash') return `Bash: ${truncate(inp.command || '', 80)}`;
    if (name === 'Read') return `Read: ${inp.file_path || ''}`;
    if (name === 'Write') return `Write: ${inp.file_path || ''}`;
    if (name === 'Edit') return `Edit: ${inp.file_path || ''}`;
    if (name === 'Glob') return `Glob: ${inp.pattern || ''}`;
    if (name === 'Grep') return `Grep: /${inp.pattern || ''}/` + (inp.path ? ` in ${inp.path}` : '');
    if (name === 'WebFetch') return `Fetch: ${truncate(inp.url || '', 80)}`;
    if (name === 'WebSearch') return `Search: ${truncate(inp.query || '', 80)}`;
    if (name === 'Task') return `Task: ${inp.subagent_type || ''} - ${inp.description || ''}`;
    if (name === 'TodoWrite') return 'TodoWrite';
    if (name === 'AskUserQuestion') return 'AskUserQuestion';
    return name;
}
