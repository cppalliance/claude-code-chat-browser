import { renderBashUse } from './tool_use/bash.js';
import { renderReadUse } from './tool_use/read.js';
import { renderWriteUse } from './tool_use/write.js';
import { renderEditUse } from './tool_use/edit.js';
import { renderGlobUse } from './tool_use/glob.js';
import { renderGrepUse } from './tool_use/grep.js';
import { renderTaskUse } from './tool_use/task.js';
import { renderTodoWriteUse } from './tool_use/todo_write.js';
import { renderAskUserQuestionUse } from './tool_use/ask_user_question.js';
import { renderWebFetchUse } from './tool_use/web_fetch.js';
import { renderWebSearchUse } from './tool_use/web_search.js';
import { renderToolUseFallback } from './tool_use/fallback.js';
import { getToolSummary } from './tool_use/summary.js';

import { renderBashResult } from './tool_result/bash.js';
import { renderFileReadResult } from './tool_result/file_read.js';
import { renderFileEditResult } from './tool_result/file_edit.js';
import { renderFileWriteResult } from './tool_result/file_write.js';
import { renderGlobResult } from './tool_result/glob.js';
import { renderGrepResult } from './tool_result/grep.js';
import { renderWebSearchResult } from './tool_result/web_search.js';
import { renderWebFetchResult } from './tool_result/web_fetch.js';
import { renderTaskResult } from './tool_result/task.js';
import { renderTodoWriteResult } from './tool_result/todo_write.js';
import { renderUserInputResult } from './tool_result/user_input.js';
import { renderPlanResult } from './tool_result/plan.js';
import { renderToolResultFallback } from './tool_result/fallback.js';
import { toolResultHasBody } from './tool_result/utils.js';

export { getToolSummary, toolResultHasBody };

export const TOOL_USE_RENDERERS = {
    Bash: renderBashUse,
    Read: renderReadUse,
    Write: renderWriteUse,
    Edit: renderEditUse,
    Glob: renderGlobUse,
    Grep: renderGrepUse,
    Task: renderTaskUse,
    TodoWrite: renderTodoWriteUse,
    AskUserQuestion: renderAskUserQuestionUse,
    WebFetch: renderWebFetchUse,
    WebSearch: renderWebSearchUse,
};

export const TOOL_RESULT_RENDERERS = {
    bash: renderBashResult,
    file_read: renderFileReadResult,
    file_edit: renderFileEditResult,
    file_write: renderFileWriteResult,
    glob: renderGlobResult,
    grep: renderGrepResult,
    web_search: renderWebSearchResult,
    web_fetch: renderWebFetchResult,
    task: renderTaskResult,
    todo_write: renderTodoWriteResult,
    user_input: renderUserInputResult,
    plan: renderPlanResult,
};

function getToolUseRenderer(name) {
    return Object.prototype.hasOwnProperty.call(TOOL_USE_RENDERERS, name)
        ? TOOL_USE_RENDERERS[name]
        : renderToolUseFallback;
}

function getToolResultRenderer(resultType) {
    return Object.prototype.hasOwnProperty.call(TOOL_RESULT_RENDERERS, resultType)
        ? TOOL_RESULT_RENDERERS[resultType]
        : renderToolResultFallback;
}

export function renderToolUse(tool) {
    const name = tool.name || 'unknown';
    return getToolUseRenderer(name)(tool);
}

export function renderToolResult(parsed) {
    const rt = parsed.result_type || 'unknown';
    return getToolResultRenderer(rt)(parsed);
}
