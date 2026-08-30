const express = require('express');
const app = express();
const PORT = 3001;

app.use(express.json());
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    next();
});

app.get('/health', (req, res) => {
    res.json({ status: "ok", mock: true });
});

app.post('/analyze/', (req, res) => {
    res.json({ message: "Mock mode - start real backend at localhost:8000" });
});

app.post('/debugging/', (req, res) => {
    res.json({ issues: [] });
});

app.post('/explanation/', (req, res) => {
    res.json({ summary: "Mock explanation" });
});

app.post('/suggestions/', (req, res) => {
    res.json({ overall_score: 50, grade: "C" });
});

app.listen(PORT, () => {
    console.log(`Mock server running on http://localhost:${PORT}`);
});