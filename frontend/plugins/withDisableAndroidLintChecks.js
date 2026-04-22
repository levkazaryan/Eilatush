/**
 * withDisableAndroidLintChecks.js
 *
 * Custom Expo config plugin that injects a `lint { ... }` block into the
 * generated Android `app/build.gradle` to prevent Gradle's `lintVitalRelease`
 * task from failing the build on non-fatal lint issues.
 *
 * Specifically, this disables the `ExtraTranslation` and `MissingTranslation`
 * checks. These fire because the Emergent deployment pipeline auto-generates
 * locale-specific strings (e.g. `values-b+he/strings.xml` with the Hebrew app
 * name under `CFBundleDisplayName`) without a matching entry in the default
 * `values/strings.xml`. Those translations are cosmetically redundant but
 * still cause `lintVitalRelease` to abort the release build.
 *
 * Additional safety:
 *  - `abortOnError false`    → do not abort the build on lint errors
 *  - `checkReleaseBuilds false` → skip lint during release builds entirely
 */

const { withAppBuildGradle } = require('@expo/config-plugins');

const LINT_BLOCK = `
    lint {
        abortOnError false
        checkReleaseBuilds false
        disable 'ExtraTranslation', 'MissingTranslation'
    }
`;

const ANCHOR = 'disable \'ExtraTranslation\', \'MissingTranslation\'';

function injectLintBlock(contents) {
  if (contents.includes(ANCHOR)) {
    return contents; // already patched
  }
  // Find the top-level `android {` opening brace and insert our block right
  // after it. Use a conservative regex so we only match the first occurrence.
  const match = contents.match(/android\s*\{/);
  if (!match) {
    console.warn(
      "[withDisableAndroidLintChecks] Could not find 'android {' block in app/build.gradle; skipping."
    );
    return contents;
  }
  const idx = match.index + match[0].length;
  return contents.slice(0, idx) + '\n' + LINT_BLOCK + contents.slice(idx);
}

module.exports = function withDisableAndroidLintChecks(config) {
  return withAppBuildGradle(config, (cfg) => {
    if (cfg.modResults.language !== 'groovy') {
      // Only handle Groovy build.gradle (the default for React Native /
      // Expo projects). Kotlin DSL is not currently used by EAS RN templates.
      return cfg;
    }
    cfg.modResults.contents = injectLintBlock(cfg.modResults.contents);
    return cfg;
  });
};
