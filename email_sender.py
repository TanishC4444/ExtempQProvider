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
        """Read and parse extemp questions from the file"""
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
        
        # Parse the content into question blocks
        question_blocks = []
        current_block = []
        
        lines = content.split('\n')
        in_question_block = False
        current_link = None
        current_info = None
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('Link: '):
                # Start of a new block
                if current_block and current_link and current_info:
                    question_blocks.append({
                        'link': current_link,
                        'info': current_info,
                        'content': '\n'.join(current_block)
                    })
                
                current_link = line
                current_info = None
                current_block = []
                in_question_block = False
                
            elif line.startswith('Info: '):
                current_info = line
                
            elif line.startswith('='):
                if 'NSDA EXTEMPORANEOUS SPEAKING QUESTIONS' in ''.join(lines[lines.index(line):lines.index(line)+3]):
                    in_question_block = True
                current_block.append(line)
                
            elif line.startswith('NSDA EXTEMPORANEOUS SPEAKING QUESTIONS'):
                in_question_block = True
                current_block.append(line)
                
            elif in_question_block and line:
                current_block.append(line)
                
            elif in_question_block and not line:
                # Empty line might end the block, but check next lines
                current_block.append(line)
        
        # Add the last block
        if current_block and current_link and current_info:
            question_blocks.append({
                'link': current_link,
                'info': current_info,
                'content': '\n'.join(current_block)
            })
        
        print(f"✅ Parsed {len(question_blocks)} question blocks from {self.extemp_file}")
        return question_blocks
    
    def read_sent_log(self):
        """Read the log of already sent questions"""
        if not os.path.exists(self.sent_log_file):
            return set()
        
        try:
            with open(self.sent_log_file, 'r', encoding='utf-8') as f:
                sent_links = set(line.strip() for line in f if line.strip())
            print(f"📋 Found {len(sent_links)} already sent questions in log")
            return sent_links
        except Exception as e:
            print(f"⚠️ Error reading sent log: {e}")
            return set()
    
    def write_sent_log(self, link):
        """Add a link to the sent log"""
        try:
            with open(self.sent_log_file, 'a', encoding='utf-8') as f:
                f.write(f"{link}\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"⚠️ Error writing to sent log: {e}")
    
    def format_email_content(self, question_blocks):
        """Format question blocks into beautiful HTML email content"""
        
        # Pre-calculate values that contain backslashes to avoid f-string issues
        current_date = datetime.now().strftime('%B %d, %Y')
        total_questions = sum(len(re.findall(r'^Q\d+\.', block['content'], re.MULTILINE)) for block in question_blocks)
        footer_timestamp = datetime.now().strftime('%A, %B %d, %Y at %I:%M %p UTC')
        
        # HTML Email Template
        html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NSDA Extemporaneous Speaking Questions</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }}
            
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                padding: 30px;
                border-radius: 10px 10px 0 0;
                margin-bottom: 0;
            }}
            
            .header h1 {{
                margin: 0;
                font-size: 2.2em;
                font-weight: 300;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }}
            
            .header .subtitle {{
                margin: 10px 0 0 0;
                font-size: 1.1em;
                opacity: 0.9;
                font-weight: 300;
            }}
            
            .container {{
                background: white;
                border-radius: 0 0 10px 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            
            .stats-bar {{
                background: #f8f9fa;
                padding: 15px 30px;
                border-bottom: 2px solid #e9ecef;
                display: flex;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 15px;
            }}
            
            .stat-item {{
                background: white;
                padding: 10px 15px;
                border-radius: 25px;
                border: 2px solid #667eea;
                color: #667eea;
                font-weight: bold;
                font-size: 0.9em;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            
            .content {{
                padding: 0;
            }}
            
            .question-block {{
                margin: 0;
                border-bottom: 3px solid #f1f3f4;
                transition: all 0.3s ease;
            }}
            
            .question-block:last-child {{
                border-bottom: none;
            }}
            
            .question-block:hover {{
                background-color: #fafbfc;
            }}
            
            .article-header {{
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white;
                padding: 20px 30px;
                border-left: 5px solid #0066cc;
            }}
            
            .article-link {{
                color: white;
                text-decoration: none;
                font-weight: 500;
                font-size: 1.05em;
                word-break: break-all;
                display: block;
                margin-bottom: 5px;
            }}
            
            .article-link:hover {{
                text-decoration: underline;
                color: #e6f3ff;
            }}
            
            .article-info {{
                font-size: 0.9em;
                opacity: 0.9;
                font-style: italic;
            }}
            
            .questions-section {{
                padding: 25px 30px;
            }}
            
            .questions-title {{
                text-align: center;
                color: #2c3e50;
                font-size: 1.3em;
                font-weight: 600;
                margin: 0 0 25px 0;
                padding-bottom: 10px;
                border-bottom: 2px solid #3498db;
                position: relative;
            }}
            
            .questions-title::after {{
                content: '';
                position: absolute;
                bottom: -2px;
                left: 50%;
                transform: translateX(-50%);
                width: 60px;
                height: 2px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            
            .question-item {{
                margin-bottom: 20px;
                padding: 18px;
                background: #f8f9ff;
                border-radius: 8px;
                border-left: 4px solid #667eea;
                box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
                transition: all 0.3s ease;
            }}
            
            .question-item:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2);
            }}
            
            .question-category {{
                font-size: 0.85em;
                font-weight: 600;
                text-transform: uppercase;
                color: #667eea;
                margin-bottom: 8px;
                letter-spacing: 1px;
            }}
            
            .domestic {{ border-left-color: #e74c3c; }}
            .domestic .question-category {{ color: #e74c3c; }}
            .domestic {{ background: #fdf2f2; }}
            
            .international {{ border-left-color: #3498db; }}
            .international .question-category {{ color: #3498db; }}
            .international {{ background: #f0f8ff; }}
            
            .mixed {{ border-left-color: #f39c12; }}
            .mixed .question-category {{ color: #f39c12; }}
            .mixed {{ background: #fefcf0; }}
            
            .question-text {{
                font-size: 1.05em;
                line-height: 1.6;
                color: #2c3e50;
                margin: 0;
                font-weight: 500;
            }}
            
            .question-number {{
                font-weight: bold;
                color: #667eea;
            }}
            
            .footer {{
                background: #2c3e50;
                color: white;
                text-align: center;
                padding: 20px;
                margin-top: 30px;
                border-radius: 10px;
            }}
            
            .footer p {{
                margin: 5px 0;
                font-size: 0.9em;
            }}
            
            .timestamp {{
                color: #95a5a6;
                font-size: 0.8em;
                font-style: italic;
            }}
            
            @media (max-width: 600px) {{
                body {{ padding: 10px; }}
                .header, .questions-section {{ padding: 20px 15px; }}
                .article-header {{ padding: 15px 20px; }}
                .stats-bar {{ 
                    flex-direction: column; 
                    align-items: center;
                    gap: 10px;
                }}
                .stat-item {{ font-size: 0.8em; }}
                .question-item {{ padding: 15px; }}
                .header h1 {{ font-size: 1.8em; }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎯 NSDA Extemporaneous Speaking Questions</h1>
            <p class="subtitle">Daily Practice Questions for Competitive Speech & Debate</p>
        </div>
        
        <div class="container">
            <div class="stats-bar">
                <div class="stat-item">📰 {len(question_blocks)} Articles</div>
                <div class="stat-item">❓ {total_questions} Questions</div>
                <div class="stat-item">📅 {current_date}</div>
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
    """
        
        # Add footer
        html_content += f"""
            </div>
        </div>
        
        <div class="footer">
            <p><strong>🏆 National Speech & Debate Association</strong></p>
            <p>Extemporaneous Speaking Practice Questions</p>
            <p class="timestamp">Generated on {footer_timestamp}</p>
            <p style="margin-top: 15px; font-size: 0.8em; opacity: 0.8;">
                💡 <em>These questions are designed to encourage analysis, evaluation, and argumentation.<br>
                Each question should be answerable with a 7-minute speech using current events and multiple sources.</em>
            </p>
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
        """Main function to process and send unsent questions"""
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
            
            # Filter out already sent questions
            new_question_blocks = [
                block for block in all_question_blocks 
                if block['link'] not in sent_links
            ]
            
            if not new_question_blocks:
                print("📧 No new questions to send - all questions have been sent already")
                return True
            
            print(f"📧 Found {len(new_question_blocks)} new question blocks to send")
            
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
            print(f"📧 Sending beautiful HTML email with {question_count} question blocks...")
            print(f"📧 Subject: {subject}")
            print(f"📧 To: {', '.join(self.recipient_emails)}")
            
            if self.send_email(subject, html_body, text_body):
                # Mark questions as sent
                for block in questions_to_send:
                    self.write_sent_log(block['link'])
                    print(f"✅ Marked as sent: {block['link'][:60]}...")
                
                print(f"🎉 Successfully sent {len(questions_to_send)} question blocks!")
                
                if len(new_question_blocks) > max_questions_per_email:
                    print(f"💡 {len(new_question_blocks) - max_questions_per_email} question blocks remaining for next run")
                
                return True
            else:
                print("❌ Failed to send email - questions not marked as sent")
                return False
                
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
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
    
    # Check required variables
    required_vars = ['SENDER_EMAIL', 'SENDER_PASSWORD', 'RECIPIENT_EMAIL']
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
    
    if missing_vars:
        print(f"\n❌ Missing required variables: {', '.join(missing_vars)}")
        print(f"Please run: python {os.path.basename(__file__)} --setup")
        return False
    else:
        print(f"\n✅ Configuration looks good!")
        return True

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
    SENDER_EMAIL      Your email address
    SENDER_PASSWORD   Your email password (use App Password for Gmail)  
    RECIPIENT_EMAIL   Who receives the questions

OPTIONAL ENVIRONMENT VARIABLES:
    SMTP_SERVER       SMTP server (default: smtp.gmail.com)
    SMTP_PORT         SMTP port (default: 587)
    MAX_QUESTIONS_PER_EMAIL  Questions per email (default: 10)
    EXTEMP_FILE       Questions file path (default: extemp_questions.txt)
    SENT_LOG_FILE     Sent log file path (default: sent_questions_log.txt)

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
    SENDER_EMAIL=me@gmail.com RECIPIENT_EMAIL=friend@email.com python {script_name}
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
    max_questions = int(os.getenv('MAX_QUESTIONS_PER_EMAIL', '1000'))
    
    success = sender.process_and_send(max_questions_per_email=max_questions)
    
    if not success:
        print(f"\n💡 Need help? Run: python {os.path.basename(__file__)} --help")
        sys.exit(1)

if __name__ == "__main__":
    main()