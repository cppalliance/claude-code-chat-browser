import { renderPlanResult } from './plan.js';
import { describeSummaryOnlyResult } from '../test_helpers.js';

describeSummaryOnlyResult(renderPlanResult, {
    suiteName: 'renderPlanResult',
    resultType: 'plan',
    label: 'Plan',
    samplePath: '.cursor/plans/sprint.md',
});
