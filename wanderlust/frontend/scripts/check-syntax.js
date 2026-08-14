/**
 * Parse every source file with the app's own Babel config.
 *
 * Metro only reports a syntax error when it reaches the broken file at
 * runtime, which on a phone means discovering it mid-demo. This walks the tree
 * up front and fails loudly, and is what CI runs.
 *
 * Usage:  npm run check
 */
const fs = require('fs');
const path = require('path');
const babel = require('@babel/core');

const ROOT = path.resolve(__dirname, '..');
const TARGETS = ['index.js', 'App.js', 'src'];
const EXTENSIONS = new Set(['.js', '.jsx']);

function walk(target) {
  const absolute = path.join(ROOT, target);
  if (!fs.existsSync(absolute)) return [];
  if (fs.statSync(absolute).isFile()) return [absolute];
  return fs
    .readdirSync(absolute)
    .flatMap((entry) => walk(path.join(target, entry)));
}

const files = TARGETS.flatMap(walk).filter((f) => EXTENSIONS.has(path.extname(f)));
const failures = [];

for (const file of files) {
  try {
    babel.transformFileSync(file, { presets: ['babel-preset-expo'], babelrc: false, configFile: false });
  } catch (error) {
    failures.push({ file: path.relative(ROOT, file), message: error.message });
  }
}

for (const failure of failures) {
  console.error(`\n✗ ${failure.file}\n  ${failure.message}`);
}

if (failures.length) {
  console.error(`\n${failures.length} of ${files.length} file(s) failed to parse.`);
  process.exit(1);
}

console.log(`✓ ${files.length} source files parsed cleanly.`);
