const path = require('path');

function sampleFixturePath(filename = 'sample-python.py') {
  return path.resolve(__dirname, 'fixtures', filename);
}

module.exports = {
  sampleFixturePath,
};