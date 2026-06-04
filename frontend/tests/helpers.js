import path from 'path';
import { fileURLToPath } from 'url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));

export function sampleFixturePath(filename = 'sample-python.py') {

  return path.resolve(__dirname, 'fixtures', filename);
}