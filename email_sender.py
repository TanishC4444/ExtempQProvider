#!/usr/bin/env python3
"""
NSDA Extemp Questions Email Sender
Reads extemp questions and sends them via email automatically
Includes configuration setup and email sending functionality
"""

import os
import smtplib
import re
import sys
import getpass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from datetime import datetime
import time

# Try to load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded configuration from .env file")
except ImportError:
    pass  # Will use environment variables
except Exception as e:
    print(f"⚠️ Error loading .env file: {e}")

class ExtempEmailSender:
    def __init__(self):
        # Email configuration - set these as environment variables for security
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.sender_email = os.getenv('SENDER_EMAIL', '')
        self.sender_password = os.getenv('SENDER_PASSWORD', '')  # Use App Password for Gmail
        
        # Support multiple recipients - comma separated
        # First check for new RECIPIENT_EMAILS, fall back to old RECIPIENT_EMAIL for compatibility
        recipient_emails_str = os.getenv('RECIPIENT_EMAILS', os.getenv('RECIPIENT_EMAIL', ''))
        if recipient_emails_str:
            self.recipient_emails = [email.strip() for email in recipient_emails_str.split(',')]
        else:
            self.recipient_emails = []
        
        # File paths
        self.extemp_file = os.getenv('EXTEMP_FILE', 'extemp_questions.txt')
        self.sent_log_file = os.getenv('SENT_LOG_FILE', 'sent_questions_log.txt')
        
    def validate_config(self):
        """Validate email configuration"""
        if not all([self.sender_email, self.sender_password]) or not self.recipient_emails:
            print("❌ Missing email configuration!")
            print("Run with --setup to configure email settings")
            return False
        return True
    
    def read_extemp_questions(self):
        """Read and parse extemp questions from the file with improved parsing"""
        if not os.path.exists(self.extemp_file):
            print(f"❌ Extemp questions file not found: {self.extemp_file}")
            return []
        
        try:
            with open(self.extemp_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Error reading extemp file: {e}")
            return []
        
        if not content.strip():
            print(f"❌ Extemp questions file is empty")
            return []
        
        # Parse the content into question blocks - improved logic
        question_blocks = []
        
        # Split content by double newlines to get major sections
        sections = re.split(r'\n\s*\n+', content.strip())
        
        current_block = None
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            lines = [line.strip() for line in section.split('\n') if line.strip()]
            
            for line in lines:
                # Look for Link: at the start of a line
                if line.startswith('Link: '):
                    # Save previous block if it exists and is complete
                    if current_block and current_block.get('link') and current_block.get('content'):
                        question_blocks.append(current_block)
                    
                    # Start new block
                    current_block = {
                        'link': line.strip(),
                        'info': None,
                        'content': '',
                        'content_lines': []
                    }
                
                # Look for Info: line
                elif line.startswith('Info: ') and current_block:
                    current_block['info'] = line.strip()
                
                # Collect all other lines as content
                elif current_block is not None:
                    current_block['content_lines'].append(line)
        
        # Process the last block
        if current_block and current_block.get('link'):
            if current_block['content_lines']:
                current_block['content'] = '\n'.join(current_block['content_lines'])
                question_blocks.append(current_block)
        
        # Clean up blocks - only keep those with substantial content
        valid_blocks = []
        for block in question_blocks:
            # Check if the block has questions (contains Q1., Q2., Q3.)
            content = block.get('content', '')
            if re.search(r'Q[1-3]\.', content) and len(content.strip()) > 50:
                valid_blocks.append(block)
                print(f"✅ Valid block: {block['link'][:60]}...")
            else:
                print(f"⚠️ Skipping incomplete block: {block['link'][:60]}...")
        
        print(f"✅ Parsed {len(valid_blocks)} valid question blocks from {self.extemp_file}")
        return valid_blocks
    
    def read_sent_log(self):
        """Read the log of already sent questions with improved format detection"""
        if not os.path.exists(self.sent_log_file):
            print("📋 No sent log found - all questions will be treated as new")
            return set()
        
        try:
            with open(self.sent_log_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                print("📋 Sent log is empty - all questions will be treated as new")
                return set()
            
            sent_links = set()
            for line in content.split('\n'):
                line = line.strip()
                if line:
                    # Handle both formats: just the URL or "Link: URL"
                    if line.startswith('Link: '):
                        sent_links.add(line)
                    else:
                        # If it's just a URL, convert to Link: format for consistency
                        sent_links.add(f"Link: {line}")
            
            print(f"📋 Found {len(sent_links)} already sent questions in log")
            return sent_links
        except Exception as e:
            print(f"⚠️ Error reading sent log: {e}")
            return set()
    
    def write_sent_log(self, link):
        """Add a link to the sent log with proper format"""
        try:
            # Ensure the link is in the correct format
            if not link.startswith('Link: '):
                link = f"Link: {link}"
            
            with open(self.sent_log_file, 'a', encoding='utf-8') as f:
                f.write(f"{link}\n")
                f.flush()
                os.fsync(f.fileno())
            print(f"📝 Added to sent log: {link[:60]}...")
        except Exception as e:
            print(f"⚠️ Error writing to sent log: {e}")
    
    def format_email_content(self, question_blocks):
        """Format question blocks into beautiful HTML email content with modern styling"""
        
        # Pre-calculate values that contain backslashes to avoid f-string issues
        current_date = datetime.now().strftime('%B %d, %Y')
        total_questions = sum(len(re.findall(r'^Q\d+\.', block['content'], re.MULTILINE)) for block in question_blocks)
        footer_timestamp = datetime.now().strftime('%A, %B %d, %Y at %I:%M %p UTC')
        
        # Modern HTML Email Template
        html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NSDA Extemporaneous Speaking Questions</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                line-height: 1.6;
                color: #1a1a1a;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .email-container {{
                max-width: 900px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(20px);
                border-radius: 24px;
                overflow: hidden;
                box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
            
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                position: relative;
                overflow: hidden;
                padding: 60px 40px;
                text-align: center;
            }}
            
            .header::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="0.5"/></pattern></defs><rect width="100" height="100" fill="url(%23grid)"/></svg>');
                opacity: 0.3;
            }}
            
            .header-content {{
                position: relative;
                z-index: 2;
            }}
            
            .header h1 {{
                font-size: clamp(2.5rem, 5vw, 3.5rem);
                font-weight: 700;
                background: linear-gradient(135deg, #ffffff, #f0f8ff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                margin-bottom: 16px;
                letter-spacing: -0.02em;
            }}
            
            .header .subtitle {{
                font-size: 1.2rem;
                color: rgba(255, 255, 255, 0.9);
                font-weight: 400;
                letter-spacing: 0.01em;
            }}
            
            .stats-section {{
                padding: 32px 40px;
                background: rgba(248, 250, 252, 0.8);
                backdrop-filter: blur(10px);
                border-bottom: 1px solid rgba(226, 232, 240, 0.5);
            }}
            
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 24px;
                max-width: 600px;
                margin: 0 auto;
            }}
            
            .stat-card {{
                background: linear-gradient(135deg, #ffffff, #f8fafc);
                padding: 24px;
                border-radius: 16px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
                border: 1px solid rgba(226, 232, 240, 0.5);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }}
            
            .stat-card:hover {{
                transform: translateY(-4px);
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
            }}
            
            .stat-icon {{
                font-size: 2rem;
                margin-bottom: 12px;
                display: block;
            }}
            
            .stat-value {{
                font-size: 1.5rem;
                font-weight: 700;
                color: #1e293b;
                margin-bottom: 4px;
            }}
            
            .stat-label {{
                font-size: 0.875rem;
                color: #64748b;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            
            .content {{
                padding: 0;
            }}
            
            .question-block {{
                margin: 0;
                border-bottom: 1px solid rgba(226, 232, 240, 0.3);
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            }}
            
            .question-block:last-child {{
                border-bottom: none;
            }}
            
            .question-block:hover {{
                background: rgba(248, 250, 252, 0.5);
            }}
            
            .article-header {{
                background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%);
                padding: 32px 40px;
                position: relative;
                overflow: hidden;
            }}
            
            .article-header::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(45deg, transparent 30%, rgba(255,255,255,0.1) 50%, transparent 70%);
                transform: translateX(-100%);
                transition: transform 0.6s;
            }}
            
            .article-header:hover::before {{
                transform: translateX(100%);
            }}
            
            .article-link {{
                color: white;
                text-decoration: none;
                font-weight: 600;
                font-size: 1.1rem;
                display: block;
                margin-bottom: 8px;
                word-break: break-word;
                position: relative;
                z-index: 2;
                transition: all 0.3s ease;
            }}
            
            .article-link:hover {{
                color: #e0f2fe;
                transform: translateX(4px);
            }}
            
            .article-info {{
                font-size: 0.9rem;
                color: rgba(255, 255, 255, 0.8);
                font-weight: 500;
                position: relative;
                z-index: 2;
            }}
            
            .questions-section {{
                padding: 48px 40px;
            }}
            
            .questions-title {{
                text-align: center;
                color: #1e293b;
                font-size: 1.75rem;
                font-weight: 700;
                margin-bottom: 40px;
                position: relative;
                letter-spacing: -0.01em;
            }}
            
            .questions-title::after {{
                content: '';
                position: absolute;
                bottom: -12px;
                left: 50%;
                transform: translateX(-50%);
                width: 80px;
                height: 4px;
                background: linear-gradient(90deg, #667eea, #764ba2);
                border-radius: 2px;
            }}
            
            .questions-grid {{
                display: grid;
                gap: 24px;
            }}
            
            .question-item {{
                background: #ffffff;
                border-radius: 16px;
                padding: 28px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
                border: 1px solid rgba(226, 232, 240, 0.5);
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
                overflow: hidden;
            }}
            
            .question-item::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 4px;
                height: 100%;
                transition: all 0.3s ease;
            }}
            
            .question-item:hover {{
                transform: translateY(-6px);
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.12);
            }}
            
            .question-category {{
                display: inline-block;
                font-size: 0.75rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                padding: 6px 12px;
                border-radius: 20px;
                margin-bottom: 16px;
                transition: all 0.3s ease;
            }}
            
            .question-text {{
                font-size: 1.125rem;
                line-height: 1.7;
                color: #334155;
                margin: 0;
                font-weight: 500;
                letter-spacing: -0.01em;
            }}
            
            /* Category-specific styling */
            .domestic::before {{
                background: linear-gradient(135deg, #ef4444, #dc2626);
            }}
            
            .domestic .question-category {{
                background: linear-gradient(135deg, #fef2f2, #fee2e2);
                color: #dc2626;
                border: 1px solid #fecaca;
            }}
            
            .international::before {{
                background: linear-gradient(135deg, #3b82f6, #2563eb);
            }}
            
            .international .question-category {{
                background: linear-gradient(135deg, #eff6ff, #dbeafe);
                color: #2563eb;
                border: 1px solid #93c5fd;
            }}
            
            .mixed::before {{
                background: linear-gradient(135deg, #f59e0b, #d97706);
            }}
            
            .mixed .question-category {{
                background: linear-gradient(135deg, #fffbeb, #fef3c7);
                color: #d97706;
                border: 1px solid #fcd34d;
            }}
            
            .footer {{
                background: linear-gradient(135deg, #1e293b, #334155);
                color: white;
                text-align: center;
                padding: 48px 40px;
                position: relative;
                overflow: hidden;
            }}
            
            .footer::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: radial-gradient(circle at 30% 20%, rgba(102, 126, 234, 0.1), transparent 50%),
                            radial-gradient(circle at 70% 80%, rgba(118, 75, 162, 0.1), transparent 50%);
            }}
            
            .footer-content {{
                position: relative;
                z-index: 2;
            }}
            
            .footer h3 {{
                font-size: 1.5rem;
                font-weight: 700;
                margin-bottom: 8px;
                background: linear-gradient(135deg, #ffffff, #e2e8f0);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
            
            .footer p {{
                margin: 8px 0;
                color: #cbd5e1;
                font-weight: 400;
            }}
            
            .timestamp {{
                color: #94a3b8;
                font-size: 0.875rem;
                font-style: italic;
                margin-top: 16px;
            }}
            
            .footer-note {{
                margin-top: 32px;
                padding-top: 24px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                font-size: 0.875rem;
                line-height: 1.6;
                color: #94a3b8;
            }}
            
            /* Responsive Design */
            @media (max-width: 768px) {{
                body {{ padding: 12px; }}
                
                .email-container {{
                    border-radius: 16px;
                }}
                
                .header {{
                    padding: 40px 24px;
                }}
                
                .header h1 {{
                    font-size: 2.25rem;
                }}
                
                .stats-section {{
                    padding: 24px;
                }}
                
                .stats-grid {{
                    grid-template-columns: 1fr;
                    gap: 16px;
                }}
                
                .stat-card {{
                    padding: 20px;
                }}
                
                .article-header,
                .questions-section,
                .footer {{
                    padding: 32px 24px;
                }}
                
                .question-item {{
                    padding: 24px;
                }}
                
                .questions-title {{
                    font-size: 1.5rem;
                    margin-bottom: 32px;
                }}
            }}
            
            @media (max-width: 480px) {{
                .header {{
                    padding: 32px 20px;
                }}
                
                .header h1 {{
                    font-size: 2rem;
                }}
                
                .header .subtitle {{
                    font-size: 1rem;
                }}
                
                .article-header,
                .questions-section,
                .footer {{
                    padding: 24px 20px;
                }}
                
                .question-item {{
                    padding: 20px;
                }}
                
                .question-text {{
                    font-size: 1rem;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <div class="header-content">
                    <h1>🎯 NSDA Extemporaneous Speaking</h1>
                    <p class="subtitle">Daily Practice Questions for Competitive Speech & Debate</p>
                </div>
            </div>
            
            <div class="stats-section">
                <div class="stats-grid">
                    <div class="stat-card">
                        <span class="stat-icon">📰</span>
                        <div class="stat-value">{len(question_blocks)}</div>
                        <div class="stat-label">Articles</div>
                    </div>
                    <div class="stat-card">
                        <span class="stat-icon">❓</span>
                        <div class="stat-value">{total_questions}</div>
                        <div class="stat-label">Questions</div>
                    </div>
                    <div class="stat-card">
                        <span class="stat-icon">📅</span>
                        <div class="stat-value">{current_date.split()[1]}</div>
                        <div class="stat-label">{current_date.split()[0]} {current_date.split()[2]}</div>
                    </div>
                </div>
            </div>
            
            <div class="content">
    """
        
        # Add each question block
        for i, block in enumerate(question_blocks, 1):
            # Extract questions from content
            content_lines = block['content'].split('\n')
            questions = []
            current_question = {}
            
            for line in content_lines:
                line = line.strip()
                if line.startswith('Category:'):
                    if current_question:
                        questions.append(current_question)
                    category = line.replace('Category:', '').strip()
                    # Determine category class
                    if 'domestic' in category.lower() and 'international' not in category.lower():
                        category_class = 'domestic'
                    elif 'international' in category.lower() and 'domestic' not in category.lower():
                        category_class = 'international'
                    else:
                        category_class = 'mixed'
                    
                    current_question = {
                        'category': category,
                        'category_class': category_class,
                        'text': ''
                    }
                elif line.startswith('Q') and '.' in line:
                    if current_question:
                        current_question['text'] = line
            
            if current_question:
                questions.append(current_question)
            
            # Clean up the link URL for display
            clean_link = block['link'].replace('Link: ', '')
            
            # Extract domain for info display
            try:
                from urllib.parse import urlparse
                domain = urlparse(clean_link).netloc
                domain_display = domain.replace('www.', '').title()
            except:
                domain_display = "News Source"
            
            html_content += f"""
            <div class="question-block">
                <div class="article-header">
                    <a href="{clean_link}" class="article-link" target="_blank" rel="noopener">
                        🔗 {clean_link}
                    </a>
                    <div class="article-info">📰 {domain_display}</div>
                </div>
                
                <div class="questions-section">
                    <h3 class="questions-title">Analytical Questions</h3>
                    <div class="questions-grid">
    """
            
            # Add questions
            for question in questions:
                html_content += f"""
                    <div class="question-item {question.get('category_class', 'mixed')}">
                        <div class="question-category">
                            {question.get('category', 'General')}
                        </div>
                        <p class="question-text">{question.get('text', '')}</p>
                    </div>
    """
            
            html_content += """
                    </div>
                </div>
            </div>
    """
        
        # Add footer
        html_content += f"""
            </div>
            
            <div class="footer">
                <div class="footer-content">
                    <h3>🏆 National Speech & Debate Association</h3>
                    <p>Extemporaneous Speaking Practice Questions</p>
                    <p class="timestamp">Generated on {footer_timestamp}</p>
                    <div class="footer-note">
                        💡 <em>These questions are designed to encourage analysis, evaluation, and argumentation.<br>
                        Each question should be answerable with a 7-minute speech using current events and multiple sources.</em>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
        
        # Also create a plain text version for compatibility
        text_content = f"Daily NSDA Extemporaneous Speaking Questions\n"
        
        # Fix the text content datetime formatting too
        text_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        text_content += f"Generated on: {text_timestamp}\n"
        text_content += "=" * 80 + "\n\n"
        
        for i, block in enumerate(question_blocks, 1):
            text_content += f"{block['link']}\n"
            if block['info']:
                text_content += f"{block['info']}\n"
            text_content += "=" * 80 + "\n"
            text_content += "NSDA EXTEMPORANEOUS SPEAKING QUESTIONS\n"
            text_content += "=" * 80 + "\n"
            
            # Extract just the questions part from the content
            content_lines = block['content'].split('\n')
            question_started = False
            
            for line in content_lines:
                if line.strip().startswith('Category:') or line.strip().startswith('Q'):
                    question_started = True
                
                if question_started and line.strip():
                    if not line.startswith('=') and 'NSDA EXTEMPORANEOUS' not in line:
                        text_content += f"{line}\n"
            
            text_content += "=" * 80 + "\n"
            
            if i < len(question_blocks):
                text_content += "\n"
        
        return html_content, text_content
    
    def send_email(self, subject, html_body, text_body):
        """Send beautiful HTML email with fallback text version to multiple recipients"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.recipient_emails)  # Multiple recipients
            msg['Subject'] = subject
            
            # Add both HTML and text versions
            text_part = MIMEText(text_body, 'plain', 'utf-8')
            html_part = MIMEText(html_body, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Create SMTP session
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                
                # Send to all recipients
                server.sendmail(self.sender_email, self.recipient_emails, msg.as_string())
            
            print(f"✅ Beautiful HTML email sent to {len(self.recipient_emails)} recipients!")
            print(f"📧 Recipients: {', '.join(self.recipient_emails)}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print("❌ SMTP Authentication failed. Check your email and password.")
            print("💡 For Gmail, use an App Password instead of your regular password.")
            return False
        except smtplib.SMTPException as e:
            print(f"❌ SMTP error occurred: {e}")
            return False
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False
    
    def process_and_send(self, max_questions_per_email=10):
        """Main function to process and send unsent questions with improved tracking"""
        try:
            # Validate configuration
            if not self.validate_config():
                return False
            
            # Read questions and sent log
            all_question_blocks = self.read_extemp_questions()
            sent_links = self.read_sent_log()
            
            if not all_question_blocks:
                print("❌ No question blocks found to send")
                return False
            
            # Filter out already sent questions with improved matching
            new_question_blocks = []
            for block in all_question_blocks:
                block_link = block['link']
                
                # Check if this exact link is in sent_links
                if block_link not in sent_links:
                    new_question_blocks.append(block)
                    print(f"📧 NEW: {block_link[:60]}...")
                else:
                    print(f"✅ SENT: {block_link[:60]}...")
            
            if not new_question_blocks:
                print("📧 No new questions to send - all questions have been sent already")
                return True
            
            print(f"\n📊 SUMMARY:")
            print(f"📊 Total question blocks found: {len(all_question_blocks)}")
            print(f"📊 Already sent: {len(all_question_blocks) - len(new_question_blocks)}")
            print(f"📊 New to send: {len(new_question_blocks)}")
            
            # Send questions in batches
            questions_to_send = new_question_blocks[:max_questions_per_email]
            
            if len(new_question_blocks) > max_questions_per_email:
                print(f"📧 Sending first {max_questions_per_email} question blocks in this batch")
                print(f"📧 Remaining {len(new_question_blocks) - max_questions_per_email} will be sent in next run")
            
            # Format email content
            html_body, text_body = self.format_email_content(questions_to_send)
            
            # Create subject with emojis
            date_str = datetime.now().strftime('%B %d, %Y')
            question_count = len(questions_to_send)
            total_individual_questions = sum(
                len(re.findall(r'^Q\d+\.', block['content'], re.MULTILINE)) 
                for block in questions_to_send
            )
            
            subject = f"🎯 NSDA Extemp Questions - {date_str} ({question_count} articles, {total_individual_questions} questions)"
            
            # Send email
            print(f"\n📧 Sending beautiful HTML email with {question_count} question blocks...")
            print(f"📧 Subject: {subject}")
            print(f"📧 To: {', '.join(self.recipient_emails)}")
            
            if self.send_email(subject, html_body, text_body):
                # Mark questions as sent
                print(f"\n✅ Email sent successfully! Marking questions as sent...")
                for block in questions_to_send:
                    self.write_sent_log(block['link'])
                
                print(f"🎉 Successfully sent {len(questions_to_send)} question blocks!")
                
                if len(new_question_blocks) > max_questions_per_email:
                    print(f"💡 {len(new_question_blocks) - max_questions_per_email} question blocks remaining for next run")
                
                return True
            else:
                print("❌ Failed to send email - questions not marked as sent")
                return False
                
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False

def create_env_file():
    """Create a .env file with email configuration"""
    print("📧 Email Configuration Setup")
    print("=" * 40)
    print("This will help you set up email sending for your extemp questions.")
    print("For Gmail, you'll need to use an App Password, not your regular password.")
    print("Learn how to create Gmail App Password: https://support.google.com/accounts/answer/185833")
    print()
    
    # Get email configuration
    sender_email = input("Enter your email address (sender): ").strip()
    if not sender_email:
        print("❌ Email address is required")
        return False
    
    print(f"\nFor Gmail users: Use an App Password, not your regular password")
    print(f"App Passwords are more secure and work better with automated scripts")
    sender_password = getpass.getpass("Enter your email password/app password: ").strip()
    if not sender_password:
        print("❌ Password is required")
        return False
    
    # Support multiple recipients
    print("\n📧 Recipient Email Addresses")
    print("You can enter multiple email addresses separated by commas")
    print("Example: person1@email.com, person2@email.com, person3@email.com")
    recipient_emails = input("Enter recipient email address(es): ").strip()
    if not recipient_emails:
        print("❌ At least one recipient email is required")
        return False
    
    # Optional configurations
    print("\n--- Optional Settings (press Enter for defaults) ---")
    smtp_server = input("SMTP Server (default: smtp.gmail.com): ").strip() or "smtp.gmail.com"
    smtp_port = input("SMTP Port (default: 587): ").strip() or "587"
    
    try:
        int(smtp_port)
    except ValueError:
        print("❌ Invalid port number, using default 587")
        smtp_port = "587"
    
    max_questions = input("Max questions per email (default: 10): ").strip() or "10"
    
    try:
        int(max_questions)
    except ValueError:
        print("❌ Invalid number, using default 10")
        max_questions = "10"
    
    # Create .env file content
    env_content = f"""# Email Configuration for Extemp Questions Sender
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# Required Settings
SENDER_EMAIL={sender_email}
SENDER_PASSWORD={sender_password}
RECIPIENT_EMAILS={recipient_emails}

# Optional Settings
SMTP_SERVER={smtp_server}
SMTP_PORT={smtp_port}
MAX_QUESTIONS_PER_EMAIL={max_questions}

# File Paths (optional)
# EXTEMP_FILE=extemp_questions.txt
# SENT_LOG_FILE=sent_questions_log.txt
"""
    
    # Write .env file
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        
        # Count recipients
        recipient_list = [email.strip() for email in recipient_emails.split(',')]
        
        print(f"\n✅ Configuration saved to .env file")
        print(f"✅ Sender: {sender_email}")
        print(f"✅ Recipients ({len(recipient_list)}): {', '.join(recipient_list)}")
        print(f"✅ SMTP: {smtp_server}:{smtp_port}")
        print(f"✅ Max questions per email: {max_questions}")
        
        print(f"\n💡 To use this configuration:")
        print(f"   pip install python-dotenv")
        print(f"   python {os.path.basename(__file__)}")
        
        print(f"\n🔒 Security Note:")
        print(f"   - The .env file contains your password")
        print(f"   - Add .env to your .gitignore file")
        print(f"   - Never commit passwords to version control")
        
        return True
        
    except Exception as e:
        print(f"❌ Error writing .env file: {e}")
        return False

def test_configuration():
    """Test the current configuration"""
    print("\n🧪 Testing Current Configuration")
    print("=" * 40)
    
    # Try to load from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded .env file")
    except ImportError:
        print("⚠️ python-dotenv not installed, using system environment variables")
        print("💡 Install with: pip install python-dotenv")
    except Exception as e:
        print(f"⚠️ Error loading .env file: {e}")
    
    # Check required variables - updated for new RECIPIENT_EMAILS format
    required_vars = ['SENDER_EMAIL', 'SENDER_PASSWORD']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if var == 'SENDER_PASSWORD':
                print(f"✅ {var}: {'*' * min(len(value), 20)}")  # Hide password
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    # Check recipient emails (both new and old format)
    recipient_emails = os.getenv('RECIPIENT_EMAILS', os.getenv('RECIPIENT_EMAIL', ''))
    if recipient_emails:
        recipient_list = [email.strip() for email in recipient_emails.split(',')]
        print(f"✅ RECIPIENT_EMAILS ({len(recipient_list)}): {', '.join(recipient_list)}")
    else:
        print(f"❌ RECIPIENT_EMAILS: Not set")
        missing_vars.append('RECIPIENT_EMAILS')
    
    # Check optional variables
    optional_vars = {
        'SMTP_SERVER': 'smtp.gmail.com',
        'SMTP_PORT': '587',
        'MAX_QUESTIONS_PER_EMAIL': '10',
        'EXTEMP_FILE': 'extemp_questions.txt',
        'SENT_LOG_FILE': 'sent_questions_log.txt'
    }
    
    print(f"\nOptional settings:")
    for var, default in optional_vars.items():
        value = os.getenv(var, default)
        print(f"📝 {var}: {value}")
    
    # Check if files exist
    print(f"\nFile checks:")
    extemp_file = os.getenv('EXTEMP_FILE', 'extemp_questions.txt')
    sent_log_file = os.getenv('SENT_LOG_FILE', 'sent_questions_log.txt')
    
    if os.path.exists(extemp_file):
        file_size = os.path.getsize(extemp_file)
        print(f"✅ Extemp file exists: {extemp_file} ({file_size} bytes)")
        
        # Quick check of file content
        try:
            with open(extemp_file, 'r', encoding='utf-8') as f:
                content = f.read()
                link_count = len(re.findall(r'^Link: ', content, re.MULTILINE))
                print(f"📊 Found {link_count} articles in extemp file")
        except Exception as e:
            print(f"⚠️ Could not read extemp file: {e}")
    else:
        print(f"❌ Extemp file missing: {extemp_file}")
    
    if os.path.exists(sent_log_file):
        try:
            with open(sent_log_file, 'r', encoding='utf-8') as f:
                sent_count = len([line for line in f if line.strip()])
                print(f"✅ Sent log exists: {sent_log_file} ({sent_count} entries)")
        except Exception as e:
            print(f"⚠️ Could not read sent log: {e}")
    else:
        print(f"📋 Sent log missing: {sent_log_file} (will be created on first send)")
    
    if missing_vars:
        print(f"\n❌ Missing required variables: {', '.join(missing_vars)}")
        print(f"Please run: python {os.path.basename(__file__)} --setup")
        return False
    else:
        print(f"\n✅ Configuration looks good!")
        
        # Test email sender creation
        try:
            sender = ExtempEmailSender()
            if sender.validate_config():
                print(f"✅ Email sender initialized successfully")
                return True
            else:
                print(f"❌ Email sender validation failed")
                return False
        except Exception as e:
            print(f"❌ Error creating email sender: {e}")
            return False

def show_help():
    """Show help information"""
    script_name = os.path.basename(__file__)
    print(f"""
📧 NSDA Extemp Questions Email Sender

USAGE:
    python {script_name}                 # Send emails with current config
    python {script_name} --setup         # Configure email settings
    python {script_name} --test          # Test current configuration
    python {script_name} --help          # Show this help

DESCRIPTION:
    Reads extemp questions from extemp_questions.txt and sends them via email.
    Tracks sent questions to avoid duplicates.
    
REQUIRED ENVIRONMENT VARIABLES:
    SENDER_EMAIL        Your email address
    SENDER_PASSWORD     Your email password (use App Password for Gmail)  
    RECIPIENT_EMAILS    Who receives the questions (comma-separated for multiple)

OPTIONAL ENVIRONMENT VARIABLES:
    SMTP_SERVER         SMTP server (default: smtp.gmail.com)
    SMTP_PORT           SMTP port (default: 587)
    MAX_QUESTIONS_PER_EMAIL  Questions per email (default: 10)
    EXTEMP_FILE         Questions file path (default: extemp_questions.txt)
    SENT_LOG_FILE       Sent log file path (default: sent_questions_log.txt)

GMAIL SETUP:
    1. Enable 2-Factor Authentication
    2. Go to Security → App Passwords  
    3. Generate app password for "Mail"
    4. Use app password as SENDER_PASSWORD

EXAMPLES:
    # First time setup
    python {script_name} --setup
    
    # Send emails
    python {script_name}
    
    # With environment variables
    SENDER_EMAIL=me@gmail.com RECIPIENT_EMAILS=friend@email.com python {script_name}
    
    # Multiple recipients
    RECIPIENT_EMAILS="person1@email.com, person2@email.com" python {script_name}

TRACKING:
    The script automatically tracks which questions have been sent in {os.getenv('SENT_LOG_FILE', 'sent_questions_log.txt')}.
    Only new questions will be sent in each run.
    Delete the log file to resend all questions.
""")

def main():
    """Main function with command line interface"""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ['--help', '-h', 'help']:
            show_help()
            return
            
        elif arg in ['--setup', 'setup', 'config', 'configure']:
            print("🔧 Extemp Questions Email Sender - Configuration")
            print("=" * 50)
            if create_env_file():
                print(f"\n🎉 Setup complete! Now run: python {os.path.basename(__file__)}")
            return
            
        elif arg in ['--test', 'test']:
            if test_configuration():
                print("\n🎉 Ready to send emails!")
            else:
                print(f"\n❌ Please run: python {os.path.basename(__file__)} --setup")
            return
            
        else:
            print(f"❌ Unknown argument: {arg}")
            print(f"Run: python {os.path.basename(__file__)} --help")
            return
    
    # Main email sending functionality
    print("📧 NSDA Extemp Questions Email Sender")
    print("=" * 50)
    
    sender = ExtempEmailSender()
    
    # Get max questions per email from environment
    max_questions = int(os.getenv('MAX_QUESTIONS_PER_EMAIL', '10'))
    
    success = sender.process_and_send(max_questions_per_email=max_questions)
    
    if not success:
        print(f"\n💡 Need help? Run: python {os.path.basename(__file__)} --help")
        sys.exit(1)

if __name__ == "__main__":
    main()