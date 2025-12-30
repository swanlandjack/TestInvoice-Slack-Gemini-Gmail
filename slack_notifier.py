"""
Slack Notifier Module
Posts invoice notifications to Slack channel for approval
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackNotifier:
    """Handles posting invoice notifications to Slack"""
    
    def __init__(self, bot_token: str = None, channel_id: str = None, channel_name: str = None):
        """
        Initialize Slack notifier
        
        Args:
            bot_token: Slack bot token (defaults to SLACK_BOT_TOKEN env var)
            channel_id: Channel ID to post to (defaults to SLACK_CHANNEL_ID env var)
            channel_name: Channel name for display (defaults to SLACK_CHANNEL_NAME env var)
        """
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN")
        self.channel_id = channel_id or os.getenv("SLACK_CHANNEL_ID")
        self.channel_name = channel_name or os.getenv("SLACK_CHANNEL_NAME", "invoice-approval")
        
        if not self.bot_token:
            raise ValueError("SLACK_BOT_TOKEN not found in environment or parameters")
        if not self.channel_id:
            raise ValueError("SLACK_CHANNEL_ID not found in environment or parameters")
        
        self.client = WebClient(token=self.bot_token)
    
    
    def format_invoice_message(
        self, 
        invoice_data: Dict[str, Any], 
        verification: Dict[str, Any],
        job_id: str = None,
        email_context: Dict[str, Any] = None
    ) -> str:
        """
        Format invoice data into Slack message text
        
        Args:
            invoice_data: Parsed invoice data from Gemini
            verification: Verification results
            job_id: Optional job tracking ID
            email_context: Optional email metadata (from, subject, etc.)
        
        Returns:
            Formatted message string
        """
        # Determine verification status
        if verification.get("all_checks_passed"):
            status_emoji = "✅"
            status_text = "PASSED"
        else:
            status_emoji = "⚠️"
            status_text = "FAILED"
        
        # Build the message
        message = f"""🧾 *Invoice Pending Approval*

📋 *Invoice Details*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vendor: {invoice_data.get('vendor', 'N/A')}
Invoice #: {invoice_data.get('invoice_number', 'N/A')}
Invoice Date: {invoice_data.get('invoice_date', 'N/A')}
Due Date: {invoice_data.get('due_date', 'N/A')}

💰 *Financial Summary*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subtotal: {invoice_data.get('currency', 'USD')} {invoice_data.get('subtotal', 0):,.2f}
Tax (8.875%): {invoice_data.get('currency', 'USD')} {invoice_data.get('tax', 0):,.2f}
Total Amount: *{invoice_data.get('currency', 'USD')} {invoice_data.get('total', 0):,.2f}*

{status_emoji} *Verification Status: {status_text}*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # Add verification details
        if verification.get("details"):
            for check, result in verification["details"].items():
                message += f"{result}\n"
        
        # Add flags if verification failed
        if verification.get("flags"):
            message += "\n⚠️ *Issues Found:*\n"
            for flag in verification["flags"]:
                message += f"  • {flag}\n"
        
        # Add metadata
        message += f"\n📎 PDF Attached Below\n"
        
        if email_context:
            if email_context.get("email_from"):
                message += f"📧 From: {email_context['email_from']}\n"
            if email_context.get("email_subject"):
                message += f"📬 Subject: {email_context['email_subject']}\n"
        
        message += f"⏰ Processed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        
        if job_id:
            message += f"🔗 Job ID: {job_id}\n"
        
        message += f"""
*Please review and reply:*
✅ approve
❌ reject
"""
        
        return message
    
    
    def post_invoice_for_approval(
        self,
        invoice_data: Dict[str, Any],
        pdf_bytes: bytes,
        job_id: str = None,
        verification: Dict[str, Any] = None,
        email_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Post invoice to Slack channel with PDF attachment
        
        Args:
            invoice_data: Parsed invoice data from Gemini
            pdf_bytes: PDF file as bytes
            job_id: Optional job tracking ID
            verification: Optional verification results
            email_context: Optional email metadata
        
        Returns:
            dict with keys:
                - success: bool
                - message_ts: str (Slack message timestamp/ID)
                - channel: str
                - pdf_url: str (Slack permalink to PDF)
                - error: str or None
        """
        result = {
            "success": False,
            "message_ts": None,
            "channel": self.channel_id,
            "pdf_url": None,
            "error": None
        }
        
        try:
            # Format the message
            if verification is None:
                verification = {"all_checks_passed": False, "details": {}}
            
            message = self.format_invoice_message(
                invoice_data=invoice_data,
                verification=verification,
                job_id=job_id,
                email_context=email_context
            )
            
            # Generate filename
            invoice_number = invoice_data.get('invoice_number', 'UNKNOWN')
            filename = f"invoice_{invoice_number}.pdf"
            
            # Upload PDF with message as comment
            response = self.client.files_upload_v2(
                channel=self.channel_id,
                file=pdf_bytes,
                filename=filename,
                title=f"Invoice {invoice_number}",
                initial_comment=message
            )
            
            # Extract results
            result["success"] = True
            result["pdf_url"] = response['file']['permalink']
            result["message_ts"] = response['file']['id']  # File ID serves as unique identifier
            
            print(f"✅ Posted to Slack: #{self.channel_name}")
            print(f"   Invoice: {invoice_number}")
            print(f"   File URL: {result['pdf_url']}")
            
        except SlackApiError as e:
            error_msg = e.response.get('error', 'Unknown error')
            result["error"] = f"Slack API Error: {error_msg}"
            print(f"❌ Slack posting failed: {error_msg}")
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            print(f"❌ Slack posting failed: {str(e)}")
        
        return result
    
    
    def verify_connection(self) -> bool:
        """
        Verify Slack connection is working
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self.client.auth_test()
            print(f"✅ Slack connection verified")
            print(f"   Workspace: {response['team']}")
            print(f"   Bot: {response['user']}")
            return True
        except SlackApiError as e:
            print(f"❌ Slack connection failed: {e.response['error']}")
            return False
        except Exception as e:
            print(f"❌ Slack connection failed: {str(e)}")
            return False


# Convenience function for simple usage
def post_to_slack(
    invoice_data: Dict[str, Any],
    pdf_bytes: bytes,
    job_id: str = None,
    verification: Dict[str, Any] = None,
    email_context: Dict[str, Any] = None,
    bot_token: str = None,
    channel_id: str = None
) -> Dict[str, Any]:
    """
    Convenience function to post invoice to Slack
    
    Args:
        invoice_data: Parsed invoice data
        pdf_bytes: PDF file bytes
        job_id: Job tracking ID
        verification: Verification results
        email_context: Email metadata
        bot_token: Optional bot token (uses env var if not provided)
        channel_id: Optional channel ID (uses env var if not provided)
    
    Returns:
        Result dictionary from post_invoice_for_approval()
    """
    notifier = SlackNotifier(bot_token=bot_token, channel_id=channel_id)
    return notifier.post_invoice_for_approval(
        invoice_data=invoice_data,
        pdf_bytes=pdf_bytes,
        job_id=job_id,
        verification=verification,
        email_context=email_context
    )
