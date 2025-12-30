# 📧 AI-Powered Invoice Processing System

**MBA Course Lab: Automated Invoice Processing with Gmail, Gemini AI, and Slack**

An educational project demonstrating enterprise automation workflows using Gmail IMAP, Google's Gemini AI for intelligent document processing, and Slack integration for approval workflows.

---

## ⚠️ SECURITY & SAFETY WARNINGS

### 🔴 CRITICAL: Never Commit Credentials

**NEVER commit the following to GitHub:**
- ❌ `.env` file (contains all secrets)
- ❌ API keys (Gemini, Slack)
- ❌ Email passwords or app passwords
- ❌ Bot tokens
- ❌ Any credentials or secrets

**This repository includes `.gitignore` to protect you, but always verify before pushing!**

### 🔒 Credential Management

**For Production Deployment:**
- ✅ Use environment variables (Render, Heroku, AWS)
- ✅ Never hardcode credentials in source files
- ✅ Use secret management services
- ✅ Rotate keys regularly
- ✅ Use principle of least privilege

**For Development:**
- ✅ Store credentials in `.env` file (LOCAL ONLY)
- ✅ Keep `.env` in `.gitignore`
- ✅ Never share `.env` file
- ✅ Use different credentials for dev/prod

### 🎓 Educational Use Only

This project is designed for **educational purposes** in an MBA AI & Technology course:
- Demonstrates real-world automation workflows
- Teaches API integration and authentication
- Shows practical AI application in business processes
- **Not production-ready** without additional security hardening

### ⚡ Cost Warnings

**API Usage Costs:**
- **Gemini AI**: Pay-per-use after free tier (15 requests/min free)
- **Gmail IMAP**: Free but has rate limits
- **Slack API**: Free tier available

**Monitor your usage** to avoid unexpected charges! Set up budget alerts in Google Cloud Console.

---

## 📚 Background

### The Business Problem

In modern businesses, invoice processing is:
- **Time-consuming**: Manual data entry from PDFs
- **Error-prone**: Human transcription mistakes
- **Slow**: Delays in approval workflows
- **Expensive**: Labor costs for routine tasks

### The Solution

This system automates the entire invoice processing pipeline:

1. **📧 Email Monitoring**: Automatically scans Gmail for invoice emails
2. **🤖 AI Extraction**: Uses Gemini AI to extract structured data from PDF invoices
3. **✓ Verification**: Validates invoice data against business rules
4. **💬 Slack Integration**: Posts to Slack channel for human approval
5. **📊 Status Tracking**: Provides API for monitoring and reporting

### Learning Objectives

Students learn:
- RESTful API design and implementation
- Third-party API integration (Gmail, Gemini, Slack)
- Authentication and authorization patterns
- Asynchronous processing and threading
- Data validation and business logic
- Error handling and resilience
- Cloud deployment (Render/Heroku)

---

## 🎯 What This Program Does

### Core Functionality

#### 1. Gmail Invoice Detection
- Connects to Gmail via IMAP protocol
- Searches for unread emails with "invoice" in subject
- Extracts PDF attachments (up to 15 MB)
- Marks emails as read after processing

#### 2. AI-Powered Data Extraction
- Sends PDF to Google's Gemini AI
- Extracts structured data:
  - Invoice number
  - Vendor name
  - Invoice date & due date
  - Line items and pricing
  - Subtotal, tax, total
  - Payment terms

#### 3. Business Rule Verification
- **Vendor validation**: Matches expected vendor name
- **Amount verification**: Validates subtotal, tax rate (8.875%), and total
- **Terms checking**: Confirms Net 30 payment terms
- **Pricing validation**: Verifies hourly rates and flat fees
- Generates pass/fail report with specific flags

#### 4. Slack Notification
- Posts formatted message to approval channel
- Uploads original PDF as attachment
- Includes verification results and warnings
- Provides approval action prompts

#### 5. Status API
- RESTful endpoints for job tracking
- Human-readable status summaries
- Verification results and Slack posting status
- Job history and error tracking

### System Architecture

```
┌─────────────┐
│   Gmail     │ ──► Unread emails with "invoice"
│   Inbox     │
└──────┬──────┘
       │ PDF Attachment
       ▼
┌─────────────┐
│   Flask     │ ──► Invoice Processing System
│   Server    │     - IMAP connection
│             │     - PDF extraction
└──────┬──────┘     - Job management
       │
       ▼
┌─────────────┐
│  Gemini AI  │ ──► OCR & Data Extraction
│     API     │     - PDF → Structured JSON
└──────┬──────┘     - Invoice fields
       │
       ▼
┌─────────────┐
│ Verification│ ──► Business Logic
│   Engine    │     - 5 validation checks
└──────┬──────┘     - Flag generation
       │
       ▼
┌─────────────┐
│   Slack     │ ──► Approval Workflow
│   Channel   │     - Formatted message
│             │     - PDF attachment
└─────────────┘     - Status tracking
```

---

## 🚀 Features

### For Students (End Users)
- ✅ Web interface for credential entry
- ✅ One-click Gmail scanning
- ✅ Real-time processing status
- ✅ Detailed verification reports
- ✅ Job history tracking

### For Instructors
- ✅ Shared Slack channel for all submissions
- ✅ Centralized monitoring
- ✅ Individual student tracking (via email)
- ✅ Cost control (students use their own API keys)

### Technical Features
- ✅ Scheduled daily email checks (14:00 UTC)
- ✅ Manual trigger via web interface or API
- ✅ Multi-threaded processing
- ✅ Error handling and recovery
- ✅ Comprehensive logging
- ✅ RESTful API with JSON responses
- ✅ Browser-based credential storage (localStorage)

---

## 📋 Prerequisites

### For Deployment (Instructor)
- Render/Heroku account (or any PaaS)
- Slack workspace with admin access
- Slack bot token and channel ID
- Basic knowledge of environment variables

### For Students
- Gmail account with 2FA enabled
- Gmail App Password
- Gemini API key (free tier available)
- Sample invoice PDF (provided)

---

## 🛠️ Installation & Deployment

### Quick Deploy to Render

#### 1. Clone Repository
```bash
git clone https://github.com/yourusername/invoice-processor.git
cd invoice-processor
```

#### 2. Create Render Web Service
- Go to https://dashboard.render.com/
- Click "New +" → "Web Service"
- Connect your GitHub repository
- Configure:
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `gunicorn app:app`
  - **Python Version**: 3.11

#### 3. Set Environment Variables

**Required:**
```bash
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL_ID=C0A51KHTLEB
```

**Optional (Recommended):**
```bash
SLACK_CHANNEL_NAME=invoice-approval
GEMINI_MODEL=gemini-2.0-flash-exp
CHECK_RECENT_DAYS=7
MAX_PDF_MB=15
DAILY_CHECK_TIME=14:00
```

**DO NOT ADD** (Students provide these):
- ❌ `GEMINI_API_KEY`
- ❌ `GMAIL_USER`
- ❌ `GMAIL_APP_PASSWORD`

#### 4. Deploy
- Click "Create Web Service"
- Wait 3-5 minutes for deployment
- Test: `https://your-app.onrender.com/health`

---

## 📖 Usage

### For Students

#### Step 1: Get Credentials

**Gemini API Key:**
1. Visit https://aistudio.google.com/apikey
2. Create API key (free tier: 15 requests/min)
3. Copy and save securely

**Gmail App Password:**
1. Enable 2FA: https://myaccount.google.com/security
2. Create app password: https://myaccount.google.com/apppasswords
3. Select "Mail" application
4. Copy 16-character password (remove spaces)

#### Step 2: Prepare Test Invoice
1. Download sample invoice PDF (from course materials)
2. Email it to yourself
3. Subject MUST contain "invoice"
4. Keep email unread

#### Step 3: Use the App
1. Go to deployed URL (instructor provides)
2. Enter credentials:
   - Gemini API Key
   - Gemini Model (select from dropdown)
   - Gmail Address
   - Gmail App Password
3. Click "💾 Save Credentials"
4. Click "🔍 Check Gmail for Invoices"
5. Wait 20-30 seconds
6. View results!

### API Endpoints

#### Health Check
```bash
GET /health
```
Returns system status and configuration.

#### Manual Gmail Check
```bash
POST /check_gmail_now
Content-Type: application/json

{
  "api_key": "AIza...",
  "model": "gemini-2.0-flash-exp",
  "email": "student@gmail.com",
  "app_pass": "abcdefghijklmnop"
}
```

#### Job Status (Enhanced with Summary)
```bash
GET /job_status?job_id=abc-123-def
```
Returns full job details with human-readable summary.

#### Job Summary (Summary Only)
```bash
GET /job_summary?job_id=abc-123-def
```
Returns just the summary without technical details.

#### List All Jobs
```bash
GET /jobs
```
Returns all processed jobs with summaries.

---

## 📊 Sample Output

### Successful Processing
```json
{
  "job_id": "89fa4b73-0a61-4b1a-9cb6-c9b2e6707195",
  "summary": {
    "status": "done",
    "message": "✅ Invoice INV-2025-0882 processed successfully - USD 32,194.88 - Verified & Posted to Slack",
    "invoice_info": {
      "invoice_number": "INV-2025-0882",
      "vendor": "Nexus Path Consulting Group LLC",
      "total": "USD 32,194.88",
      "date": "2025-12-24",
      "due_date": "2026-01-23"
    },
    "verification_summary": {
      "all_checks_passed": true,
      "checks_passed": "5/5",
      "status": "✅ VERIFIED"
    },
    "slack_summary": {
      "posted": true,
      "status": "✅ Posted to Slack",
      "channel": "#invoice-approval",
      "pdf_url": "https://ordinaryaijedi.slack.com/files/..."
    }
  }
}
```

---

## 🏗️ Project Structure

```
invoice-processor/
├── app.py                      # Main Flask application
├── slack_notifier.py           # Slack integration module
├── requirements.txt            # Python dependencies
├── index.html                  # Student web interface
├── .gitignore                  # Git ignore rules (includes .env)
├── README.md                   # This file
│
├── docs/                       # Documentation
│   ├── DEPLOYMENT_GUIDE.md     # Full deployment instructions
│   ├── STUDENT_GUIDE.md        # Student instructions
│   ├── FLOW_DIAGRAMS.md        # System architecture diagrams
│   └── API_REFERENCE.md        # API documentation
│
└── samples/                    # Sample files
    └── sample_invoice.pdf      # Test invoice for students
```

---

## 🔧 Configuration

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | ✅ Yes | - | Slack bot authentication token |
| `SLACK_CHANNEL_ID` | ✅ Yes | - | Target Slack channel ID |
| `SLACK_CHANNEL_NAME` | No | `invoice-approval` | Channel name (display only) |
| `GEMINI_MODEL` | No | `gemini-2.0-flash-exp` | Gemini AI model to use |
| `CHECK_RECENT_DAYS` | No | `7` | How far back to search emails |
| `MAX_PDF_MB` | No | `15` | Maximum PDF size in MB |
| `DAILY_CHECK_TIME` | No | `14:00` | UTC time for scheduled check |
| `PORT` | No | `10000` | Server port (Render sets this) |

### Verification Rules

The system validates invoices against these rules:

1. **Vendor Match**: `"Nexus Path Consulting Group LLC"` (case-insensitive)
2. **Subtotal**: `$29,570.50` (±$0.01 tolerance)
3. **Tax Rate**: `8.875%` of subtotal
4. **Total**: `$32,194.88` (±$0.01 tolerance)
5. **Net 30 Terms**: Due date = Invoice date + 30 days

To customize, edit the `verify_invoice()` function in `app.py`.

---

## 🐛 Troubleshooting

### Common Issues

#### "No invoices found"
- ✓ Email subject contains "invoice"
- ✓ Email is unread
- ✓ Email sent within `CHECK_RECENT_DAYS`
- ✓ PDF is attached

#### "Authentication failed"
- ✓ Using Gmail App Password (not regular password)
- ✓ 2FA enabled on Gmail account
- ✓ App Password has no spaces
- ✓ Created for "Mail" application

#### "Invalid API key"
- ✓ Gemini API key starts with `AIza`
- ✓ No extra spaces when copying
- ✓ Key is active in Google AI Studio

#### "Slack posting failed"
- ✓ Bot invited to channel: `/invite @BotName`
- ✓ `SLACK_CHANNEL_ID` is correct
- ✓ Bot has `chat:write` and `files:write` permissions

#### "Module not found: slack_notifier"
- ✓ `slack_notifier.py` is in repository
- ✓ File not in `.gitignore`
- ✓ Deployment uploaded all files

---

## 🎓 Educational Notes

### Technologies Demonstrated

**Backend:**
- Flask (Python web framework)
- Gunicorn (WSGI server)
- Threading (concurrent processing)
- IMAP protocol (email access)

**APIs & Integration:**
- Google Gemini AI API
- Gmail IMAP
- Slack Web API
- RESTful API design

**DevOps:**
- Environment variable management
- Cloud deployment (Render/Heroku)
- Git version control
- Secret management

### Learning Path

**Lab 1: Gmail + Gemini**
- Email monitoring
- PDF extraction
- AI-powered OCR

**Lab 2: Verification**
- Business rule validation
- Data quality checks
- Error handling

**Lab 3: Slack Integration**
- API authentication
- File uploads
- Message formatting

**Lab 4: Deployment**
- Cloud hosting
- Environment variables
- Production best practices

---

## 📝 License

This project is for educational use in the HKUST MBA AI & Technology course.

**Not licensed for commercial use.**

---

## 👨‍🏫 Course Information

**Instructor**: Jack Lau  
**Course**: MBA - AI and Web Technologies  


---

## 🤝 Contributing

This is an educational project for a specific course. 

**For students**: Follow the lab instructions provided in class.

**For instructors**: Feel free to fork and adapt for your own courses.

---

## 📧 Support

**For Students:**
- Course Slack: `#invoice-lab`
- Office Hours: [As announced in class]
- Email: [Course email]

**For Instructors:**
- See `docs/DEPLOYMENT_GUIDE.md` for detailed setup
- See `docs/FLOW_DIAGRAMS.md` for architecture
- Open GitHub issue for technical questions

---

## ⚡ Quick Start Checklist

### Deployment (Instructor)
- [ ] Fork/clone repository
- [ ] Create Render account
- [ ] Set up Slack bot and get token
- [ ] Deploy to Render
- [ ] Add environment variables (Slack credentials)
- [ ] Test `/health` endpoint
- [ ] Share URL with students

### Student Setup
- [ ] Get Gemini API key
- [ ] Enable Gmail 2FA
- [ ] Create Gmail App Password
- [ ] Download sample invoice PDF
- [ ] Email invoice to yourself (subject: "invoice")
- [ ] Open instructor's deployed URL
- [ ] Enter credentials
- [ ] Process invoice
- [ ] Check Slack channel for result

---

## 🔗 Additional Resources

- [Gemini API Documentation](https://ai.google.dev/)
- [Gmail IMAP Guide](https://developers.google.com/gmail/imap/imap-smtp)
- [Slack API Documentation](https://api.slack.com/)
- [Render Deployment Guide](https://render.com/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)

---

## 🎯 Expected Results

When working correctly, students should see:

1. **Web Interface**: Form with 4 credential fields
2. **Processing Time**: 20-30 seconds per invoice
3. **Extraction Success**: All invoice fields populated
4. **Verification**: 5/5 checks passed (or specific failures flagged)
5. **Slack Post**: Invoice appears in `#invoice-approval` channel
6. **Status Summary**: Human-readable message like:
   - `"✅ Invoice INV-2025-0882 processed successfully - USD 32,194.88 - Verified & Posted to Slack"`

---

## 🙏 Acknowledgments

Built with:
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Google Gemini AI](https://ai.google.dev/) - Document intelligence
- [Slack API](https://api.slack.com/) - Team collaboration
- [Render](https://render.com/) - Cloud hosting

---

**⚠️ Remember: NEVER commit credentials to Git! Always check `.gitignore` before pushing!**

---

*Last updated: December 2025*
