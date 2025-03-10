"""
Script to download the latest pension agreements from SKR.
"""
import os
import requests
from pathlib import Path
from bs4 import BeautifulSoup
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# URLs
BASE_URL = "https://skr.se"
AKAP_KR_URL = f"{BASE_URL}/skr/arbetsgivarekollektivavtal/kollektivavtal/pensionerochavtalsforsakringar/tjanstepension/avgiftsbestamdkollektivavtaladpensionakapkr.74409.html"

def setup_directories():
    """Create necessary directories if they don't exist."""
    # Create docs directory in the project root
    docs_dir = Path(__file__).parent.parent / "docs"
    agreements_dir = docs_dir / "agreements"
    
    for directory in [docs_dir, agreements_dir]:
        directory.mkdir(exist_ok=True)
        logger.info(f"Created directory: {directory}")
    
    return agreements_dir

def download_file(url: str, output_path: Path) -> bool:
    """
    Download a file from URL and save it to output_path.
    
    Args:
        url: URL to download from
        output_path: Path to save the file to
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Successfully downloaded: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return False

def find_agreement_links(url: str) -> list:
    """
    Find PDF links to pension agreements on the page.
    
    Args:
        url: Page URL to search
        
    Returns:
        list: List of tuples (filename, url) for found PDFs
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for PDF links containing relevant keywords
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text().lower()
            
            # Check if it's a pension agreement PDF
            if (href.endswith('.pdf') and 
                ('akap' in text.lower() or 'kap-kl' in text.lower() or 
                 'pensionsavtal' in text.lower())):
                
                # Get filename from either the link text or the URL
                filename = text.strip().replace(' ', '_') + '.pdf'
                if not any(c.isalnum() for c in filename):
                    filename = href.split('/')[-1]
                
                # Make sure the URL is absolute
                if not href.startswith('http'):
                    href = BASE_URL + href if href.startswith('/') else BASE_URL + '/' + href
                
                links.append((filename, href))
                logger.info(f"Found agreement link: {filename} -> {href}")
        
        return links
        
    except Exception as e:
        logger.error(f"Error finding agreement links: {str(e)}")
        return []

def main():
    """Main function to download pension agreements."""
    # Setup directories
    agreements_dir = setup_directories()
    
    # Find and download agreements
    logger.info("Searching for pension agreements...")
    links = find_agreement_links(AKAP_KR_URL)
    
    if not links:
        logger.warning("No agreement PDFs found!")
        return
    
    # Download each found agreement
    for filename, url in links:
        output_path = agreements_dir / filename
        if download_file(url, output_path):
            logger.info(f"Successfully downloaded {filename}")
        else:
            logger.error(f"Failed to download {filename}")

if __name__ == "__main__":
    main() 