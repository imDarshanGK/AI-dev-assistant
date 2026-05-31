const fs = require('fs');
const path = require('path');

const htmlPath = path.resolve(__dirname, '..', 'frontend', 'index.html');
const htmlContent = fs.readFileSync(htmlPath, 'utf8');

const regex = /<script\b[^>]*>([\s\S]*?)<\/script>/gi;
let match;
let index = 0;

while ((match = regex.exec(htmlContent)) !== null) {
  const content = match[1];
  if (!content.trim()) continue;
  index++;
  console.log(`Parsing Script #${index}...`);
  try {
    new Function(content);
    console.log(`Script #${index} parsed successfully.`);
  } catch (err) {
    console.error(`Syntax Error in Script #${index}:`, err);
    console.error(err.stack);
  }
}
