# 🚀 Womba Jira Connect App - Quick Start

## ⚡ 30-Second Deploy

```bash
# 1. Deploy to Render
git add . && git commit -m "Add Jira integration" && git push

# 2. Set environment variable on Render
WOMBA_BASE_URL=https://womba.onrender.com

# 3. Install in Jira
# Go to: https://your-company.atlassian.net/plugins/servlet/upm
# Click "Upload app"
# Enter: https://womba.onrender.com/atlassian-connect.json
```

## ✅ Verify It Works

```bash
# Test descriptor
curl https://womba.onrender.com/atlassian-connect.json

# Test health
curl https://womba.onrender.com/health

# Should both return 200 OK
```

## 📋 Installation Checklist

- [ ] Code pushed to GitHub
- [ ] Render deployed successfully
- [ ] `WOMBA_BASE_URL` set on Render
- [ ] Descriptor accessible at `/atlassian-connect.json`
- [ ] Jira development mode enabled
- [ ] App installed in Jira
- [ ] Womba panel appears on issues
- [ ] API keys configured in admin

## 🧪 Test Locally First (5 minutes)

```bash
# Terminal 1
python -m uvicorn src.api.main:app --port 8000

# Terminal 2  
ngrok http 8000

# Terminal 3
curl https://YOUR-URL.ngrok.io/atlassian-connect.json

# Then install in Jira using YOUR-URL.ngrok.io
```

## 🎯 What You Get

✅ **Issue Panel** - Generate tests from any issue  
✅ **Test Badge** - See test count on every issue  
✅ **Admin Config** - Centralized API key management  
✅ **Test Manager** - Bulk operations and history  
✅ **Auto-Upload** - Tests go straight to Zephyr  
✅ **Multi-Tenant** - Multiple Jira instances supported  

## 📚 Documentation

- **Installation**: `JIRA_INSTALLATION_GUIDE.md`
- **Technical**: `ATLASSIAN_CONNECT_TECHNICAL.md`  
- **Testing**: `TESTING_SUMMARY.md`
- **Complete**: `WHATS_DONE.md`

## 🆘 Quick Fixes

**"Descriptor not loading"**
→ Check Render is running: `https://womba.onrender.com/health`

**"Installation failed"**
→ Enable Jira development mode first

**"Panel not showing"**
→ Refresh page, check app is enabled in Jira

**"JWT errors"**
→ Reinstall the app to refresh secrets

## 🎉 You're Done!

**Everything is implemented and tested.**  
**Just deploy and install in Jira!**

---

Need help? Check the full guides in the repo root.

