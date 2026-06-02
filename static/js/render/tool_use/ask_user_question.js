import { esc } from '../../shared/utils.js';
import { getToolSummary } from './summary.js';
import { wrapToolUse } from './common.js';

export function renderAskUserQuestionUse(tool) {
    const inp = tool.input || {};
    const summary = getToolSummary('AskUserQuestion', inp);
    let body = '';
    const questions = inp.questions || [];
    for (const q of questions) {
        body += `<div class="tool-call-section"><strong>Q:</strong> ${esc(q.question || '')}</div>`;
    }
    return wrapToolUse(summary, body);
}
