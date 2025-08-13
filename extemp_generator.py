import os
import re
from llama_cpp import Llama
from urllib.parse import urlparse
import time
import shutil

# Initialize your LLaMA model with optimized settings
MODEL_PATH = os.getenv('MODEL_PATH', '/Users/tanishchauhan/Desktop/CEUIL_AI copy/mistral-7b-instruct-v0.1.Q4_K_M.gguf')

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,
    n_gpu_layers=-1,
    n_threads=8,
    n_batch=512,
    use_mlock=True,
    use_mmap=True,
    verbose=False
)

# NSDA Extemp prompt template focusing on analysis and argumentation
PROMPT_TEMPLATE = """Create exactly 3 NSDA Extemporaneous Speaking questions from this news article.

STRICT REQUIREMENTS FOR NSDA EXTEMP QUESTIONS:
- Questions must encourage ANALYSIS, EVALUATION, and ARGUMENTATION (not just factual recall)
- Focus on implications, causes, effects, solutions, comparisons, and future predictions
- Questions should be answerable with a 7-minute speech using this article as ONE source
- Each question must be clear, specific, and debatable
- Questions should allow for multiple valid perspectives and arguments
- Use question stems that promote critical thinking: "Should...", "What are the implications of...", "How effective...", "To what extent...", "What factors...", etc.
- Questions must be relevant to current domestic or international issues
- Avoid questions that can be answered with simple yes/no or single facts
- Don't to multiple parts or sub-questions in a single question, no "ands" or "ors"

QUESTION TYPES TO FOCUS ON:
- Policy analysis and evaluation
- Cause and effect relationships
- Future implications and predictions
- Comparative analysis
- Solution-oriented questions
- Stakeholder impact analysis

FORMAT (follow exactly):
Category: [Domestic/International]
Q1. [Analytical question that encourages argumentation and uses the article's topic]

Category: [Domestic/International] 
Q2. [Analytical question that encourages argumentation and uses the article's topic]

Category: [Domestic/International]
Q3. [Analytical question that encourages argumentation and uses the article's topic]

Article: {article}

Generate exactly 3 analytical extemp questions now:
"""

def read_articles(filename):
    """Read articles from file and return list of (link, article) tuples with improved parsing"""
    if not os.path.exists(filename):
        print(f"Input file {filename} does not exist!")
        return []
        
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {filename}: {e}")
        return []

    if not content.strip():
        print(f"Input file {filename} is empty!")
        return []

    articles = []
    # Normalize line endings first
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Split by double newline, but be more flexible
    article_blocks = re.split(r'\n\s*\n+', content.strip())
    
    for block in article_blocks:
        block = block.strip()
        if not block:
            continue
            
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        
        current_link = None
        article_lines = []
        in_article = False
        
        for line in lines:
            if line.startswith("Link: "):
                current_link = line
                in_article = False
                article_lines = []
            elif line.startswith("Article: "):
                # Start collecting article text
                article_content = line[len("Article: "):].strip()
                if article_content:  # If there's content on the same line
                    article_lines = [article_content]
                else:
                    article_lines = []
                in_article = True
            elif in_article and current_link:
                # Continue collecting article text
                article_lines.append(line)
        
        # Join all article lines and add to articles list
        if current_link and article_lines:
            current_article = ' '.join(article_lines).strip()
            if current_article and len(current_article) > 50:  # Only add substantial articles
                articles.append((current_link, current_article))
                print(f"✓ Parsed article: {current_link[:60]}...")
    
    print(f"Successfully parsed {len(articles)} articles from {filename}")
    return articles

def write_articles_to_file(filename, articles):
    """Write articles to file with proper formatting"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            if articles:
                for i, (link, article) in enumerate(articles):
                    f.write(f"{link}\n")
                    f.write(f"Article: {article}\n")
                    if i < len(articles) - 1:  # Add separator between articles
                        f.write("\n")
            # Force write to disk
            f.flush()
            os.fsync(f.fileno())
        return True
    except Exception as e:
        print(f"Error writing to file {filename}: {e}")
        return False

def create_backup(filename):
    """Create backup of the input file"""
    try:
        backup_filename = filename + '.backup'
        if os.path.exists(filename):
            shutil.copy2(filename, backup_filename)
            print(f"✓ Created backup: {backup_filename}")
            return backup_filename
        return None
    except Exception as e:
        print(f"Error creating backup: {e}")
        return None

def restore_from_backup(filename, backup_filename):
    """Restore from backup file"""
    try:
        if backup_filename and os.path.exists(backup_filename):
            shutil.copy2(backup_filename, filename)
            print(f"✅ Restored from backup: {backup_filename}")
            return True
        return False
    except Exception as e:
        print(f"Error restoring from backup: {e}")
        return False

def chunk_text(text, max_words=800):
    """Chunk text by words, ensuring we don't split sentences - larger chunks for extemp context"""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())
        
        # If adding this sentence would exceed limit, start new chunk
        if current_word_count + sentence_words > max_words and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_word_count = sentence_words
        else:
            current_chunk.append(sentence)
            current_word_count += sentence_words

    # Add the last chunk if it has content
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def extract_headline_from_url(url):
    """Extract a readable headline from the URL"""
    try:
        # Try to get headline from URL structure
        if '/articles/' in url:
            # BBC style URLs
            article_id = url.split('/articles/')[-1].split('?')[0]
            return f"BBC News Article ({article_id})"
        elif '/news/' in url:
            # Other news URLs
            parts = url.split('/')
            if len(parts) > 4:
                return f"News Article: {parts[-1].replace('-', ' ').replace('.html', '').title()}"
    except:
        pass
    
    # Fallback to domain name
    try:
        domain = urlparse(url).netloc
        return f"News Article from {domain}"
    except:
        return "News Article"

def generate_extemp_questions(article_text):
    """Generate NSDA Extemp questions from article text"""
    # Use larger chunks for extemp since questions need more context
    word_count = len(article_text.split())
    
    if word_count > 1000:
        # Use larger chunks for better context
        chunks = chunk_text(article_text, max_words=1000)
        chunk = chunks[0]  # Use first chunk
    else:
        chunk = article_text
    
    print(f"Processing chunk ({len(chunk.split())} words)...")
    
    if len(chunk.split()) < 150:  # Extemp needs more context than MCQ
        print("Chunk too short for quality extemp questions, skipping...")
        return ""
    
    prompt = PROMPT_TEMPLATE.format(article=chunk)
    
    try:
        start_time = time.time()
        
        response = llm(
            prompt,
            max_tokens=400,  # Slightly more tokens for analytical questions
            temperature=0.2,  # Slightly higher for more creative question formation
            top_p=0.9,
            stop=["Article:", "\n\nHere", "Instructions:", "Note:"],
            echo=False
        )
        
        generation_time = time.time() - start_time
        print(f"Generated in {generation_time:.1f}s")
        
        output = response['choices'][0]['text'].strip()
        
        # Validate extemp questions - check for analytical nature
        if 'Q1.' in output and 'Q2.' in output and 'Q3.' in output:
            # Check if questions are analytical (contain key analytical words)
            analytical_indicators = [
                'should', 'how', 'what are the implications', 'to what extent', 
                'why', 'what factors', 'how effective', 'what impact', 
                'how will', 'what role', 'analyze', 'evaluate', 'compare'
            ]
            
            output_lower = output.lower()
            analytical_count = sum(1 for indicator in analytical_indicators if indicator in output_lower)
            
            if analytical_count >= 2:  # At least 2 questions should be analytical
                return output
            else:
                print("Generated questions not sufficiently analytical for extemp")
                return ""
        else:
            print("Generated output missing required questions")
            return ""
            
    except Exception as e:
        print(f"Error generating extemp questions: {e}")
        return ""

def main():
    """Main function to process articles and generate NSDA Extemp questions"""
    input_file = os.getenv('INPUT_FILE', '/Users/tanishchauhan/Desktop/CEUIL_AI/articles/news_articles.txt')
    
    print(f"🔍 Reading articles from: {input_file}")
    print(f"📁 Input file exists: {os.path.exists(input_file)}")
    if os.path.exists(input_file):
        print(f"📄 Input file size: {os.path.getsize(input_file)} bytes")
    
    # Create backup before processing
    backup_filename = create_backup(input_file)
    
    # Read all articles at start
    all_articles = read_articles(input_file)
    print(f"Found {len(all_articles)} total articles to process")
    
    if not all_articles:
        print("No articles found in the input file!")
        return
    
    # Process articles one by one and remove them immediately after processing
    batch_size = min(5, len(all_articles))  # Process in smaller batches for better reliability
    print(f"📋 Processing {batch_size} articles in this batch...")
    
    successful_count = 0
    processed_articles = []  # Keep track of successfully processed articles
    start_time = time.time()
    
    # Open extemp questions file in append mode
    with open('extemp_questions.txt', 'a', encoding='utf-8') as out:
        for i in range(min(batch_size, len(all_articles))):
            link, article = all_articles[i]
            
            print(f"\n--- Processing article {i+1}/{batch_size} ---")
            elapsed = time.time() - start_time
            avg_time = elapsed / (i + 1) if i > 0 else 0
            est_remaining = avg_time * (batch_size - i - 1)
            
            print(f"Link: {link}")
            print(f"Article length: {len(article.split())} words")
            print(f"Elapsed: {elapsed/60:.1f}min, Avg: {avg_time:.1f}s/article")
            print(f"Est. remaining: {est_remaining/60:.1f}min")

            # Skip articles that are too short for quality extemp questions
            if len(article.split()) < 150:
                print("Article too short for quality extemp questions, skipping...")
                # Still count as processed so it gets removed from the file
                processed_articles.append((link, article))
                continue

            # Extract headline from URL
            article_info = extract_headline_from_url(link)
            
            # Generate Extemp questions
            questions = generate_extemp_questions(article)
            
            # Write to output file
            out.write(f"\n{link}\n")
            out.write(f"Info: {article_info}\n")
            out.write("="*80 + "\n")
            out.write("NSDA EXTEMPORANEOUS SPEAKING QUESTIONS\n")
            out.write("="*80 + "\n")
            
            if questions.strip():
                out.write(questions + '\n\n')
                successful_count += 1
                print("✅ Extemp questions generated successfully")
            else:
                out.write("No valid extemp questions could be generated for this article.\n\n")
                print("❌ Failed to generate valid extemp questions")
                
            out.write("="*80 + "\n\n")
            out.flush()  # Ensure content is written immediately
            
            # Mark this article as processed (regardless of success/failure)
            processed_articles.append((link, article))
            
            # Update the input file to remove processed articles after every few articles
            if (i + 1) % 10 == 0 or i == batch_size - 1:  # Update every 10 articles or at the end
                remaining_articles = all_articles[len(processed_articles):]
                print(f"\n📝 Updating input file (removing {len(processed_articles)} processed articles)...")
                
                # Try to write the updated file
                max_retries = 3
                update_success = False
                
                for attempt in range(max_retries):
                    if write_articles_to_file(input_file, remaining_articles):
                        # Verify the write
                        verification_articles = read_articles(input_file)
                        if len(verification_articles) == len(remaining_articles):
                            print(f"✅ Successfully updated input file: {len(remaining_articles)} articles remaining")
                            update_success = True
                            break
                        else:
                            print(f"⚠️ Write verification failed: expected {len(remaining_articles)}, found {len(verification_articles)}")
                    
                    if attempt < max_retries - 1:
                        print(f"⚠️ Update attempt {attempt + 1} failed, retrying in 1 second...")
                        time.sleep(1)
                
                if not update_success:
                    print("❌ Failed to update input file after all attempts")
                    if backup_filename:
                        restore_from_backup(input_file, backup_filename)
                    return
    
    total_time = time.time() - start_time
    print(f"\n✅ Batch complete: {successful_count}/{len(processed_articles)} articles processed successfully in {total_time/60:.1f} minutes")
    
    # Final verification
    print(f"\n🔍 Final verification...")
    final_articles = read_articles(input_file)
    expected_remaining = len(all_articles) - len(processed_articles)
    actual_remaining = len(final_articles)
    
    print(f"✅ Final status:")
    print(f"   - Original articles: {len(all_articles)}")
    print(f"   - Processed articles: {len(processed_articles)}")
    print(f"   - Expected remaining: {expected_remaining}")
    print(f"   - Actual remaining: {actual_remaining}")
    print(f"   - Match: {'✅ YES' if expected_remaining == actual_remaining else '❌ NO'}")
    
    # Clean up backup if everything went well
    if backup_filename and expected_remaining == actual_remaining:
        try:
            os.remove(backup_filename)
            print(f"🗑️ Cleaned up backup file")
        except:
            print(f"⚠️ Could not clean up backup file: {backup_filename}")
    
    # Show final status
    print(f"\n📊 FINAL STATUS:")
    print(f"📊 Articles processed this run: {len(processed_articles)}")
    print(f"📊 Articles with successful extemp questions: {successful_count}")
    print(f"📊 Remaining articles for next run: {actual_remaining}")
    
    if actual_remaining > 0:
        print("💡 Next run will process more articles")
    else:
        print("🎉 All articles have been processed!")

if __name__ == "__main__":
    main()