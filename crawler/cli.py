import argparse
import sys
from pathlib import Path
from main import run_spider

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Web Crawler CLI - Crawl websites and extract content',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python cli.py -u https://example.com
  python cli.py --url https://example.com
        '''
    )
    
    # Add arguments
    parser.add_argument(
        '-u', '--url',
        required=True,
        help='Target URL to crawl (required)',
        type=str
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output directory for crawled data (default: data/crawled_data)',
        default='data/crawled_data',
        type=str
    )

    parser.add_argument(
        '-r', '--recursive',
        help='Crawl recursively through all linked pages',
        action='store_true'
    )
    
    # Parse arguments
    try:
        args = parser.parse_args()
    except SystemExit as e:
        # Catch the system exit for --help or errors
        if e.code == 0:
            return 0  # Help message was displayed
        return 1  # Error occurred
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nStarting crawler...")
    print(f"Target URL: {args.url}")
    print(f"Output directory: {output_dir}")
    print(f"Recursive mode: {args.recursive}\n")
    
    try:
        # Run the crawler
        results = run_spider(args.url, recursive=args.recursive)
        
        if results:
            print(f"\nCrawling completed successfully!")
            print(f"Crawled {len(results)} pages")
            print(f"Results saved in: {output_dir}")
        else:
            print("\nNo data was crawled. Please check the URL and try again.")
            return 1
            
        return 0
        
    except Exception as e:
        print(f"\nError during crawling: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 