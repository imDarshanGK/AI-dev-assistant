import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export function sampleFixturePath(filename = 'sample-python.py') {
  return path.resolve(__dirname, 'fixtures', filename);
}