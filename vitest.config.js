import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        include: ['static/js/**/*.test.js'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'lcov'],
            include: ['static/js/**/*.js'],
            exclude: ['static/js/**/*.test.js', 'static/js/**/test_helpers.js'],
            thresholds: {
                lines: 85,
                functions: 75,
                branches: 55,
            },
        },
    },
});
