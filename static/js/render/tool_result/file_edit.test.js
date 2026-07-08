import { renderFileEditResult } from './file_edit.js';
import { describeSummaryOnlyResult } from '../test_helpers.js';

describeSummaryOnlyResult(renderFileEditResult, {
    suiteName: 'renderFileEditResult',
    resultType: 'file_edit',
    label: 'Edited',
    samplePath: 'src/app.js',
});
