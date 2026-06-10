# Maintainer Guide

## 1. Deploy Steps
- [ ] Pull latest code: `git pull origin main`
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Run application: `python app.py`
- [ ] Verify service is running on port 8000

## 2. Rollback Steps
- [ ] Find last stable commit: `git log --oneline`
- [ ] Revert to that commit: `git revert <commit-hash>`
- [ ] Restart service: `systemctl restart ai-dev-assistant`

## 3. Monitoring
- [ ] Check logs: `tail -f logs/app.log`
- [ ] Check API health: `curl http://localhost:8000/health`
- [ ] Monitor CPU/Memory usage
- [ ] Set up alerts for downtime