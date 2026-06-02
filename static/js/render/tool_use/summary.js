import { esc, truncate } from '../../shared/utils.js';

export function getToolSummary(name, inp) {
    if (name === 'Bash') return `Bash: ${truncate(inp.command || '', 80)}`;
    if (name === 'Read') return `Read: ${esc(inp.file_path || '')}`;
    if (name === 'Write') return `Write: ${esc(inp.file_path || '')}`;
    if (name === 'Edit') return `Edit: ${esc(inp.file_path || '')}`;
    if (name === 'Glob') return `Glob: ${esc(inp.pattern || '')}`;
    if (name === 'Grep') return `Grep: /${esc(inp.pattern || '')}/` + (inp.path ? ` in ${esc(inp.path)}` : '');
    if (name === 'WebFetch') return `Fetch: ${truncate(inp.url || '', 80)}`;
    if (name === 'WebSearch') return `Search: ${truncate(inp.query || '', 80)}`;
    if (name === 'Task') return `Task: ${esc(inp.subagent_type || '')} - ${esc(inp.description || '')}`;
    if (name === 'TodoWrite') return 'TodoWrite';
    if (name === 'AskUserQuestion') return 'AskUserQuestion';
    return name;
}
