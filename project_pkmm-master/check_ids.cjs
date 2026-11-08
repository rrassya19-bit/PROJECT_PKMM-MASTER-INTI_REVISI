const fs = require('fs');
const html = fs.readFileSync(__dirname + '/static/index.html', 'utf8');
const regex = /id=["']([^"']+)["']/g;
const ids = [];
let match;
while ((match = regex.exec(html)) !== null) {
  ids.push(match[1]);
}
const seen = new Set();
const duplicates = [];
for (const id of ids) {
  if (seen.has(id)) duplicates.push(id);
  seen.add(id);
}
console.log('Total IDs found:', ids.length);
console.log('Duplicate IDs:', duplicates);

