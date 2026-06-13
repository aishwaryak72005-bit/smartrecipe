import urllib.request
import urllib.parse as _urlparse
import re

def scrape_bing_image(query):
    url = f"https://www.bing.com/images/search?q={_urlparse.quote(query + ' cooked dish meal food photography')}&form=HDRSC2"
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    html = urllib.request.urlopen(req, timeout=4).read().decode('utf-8')
    matches = re.findall(r'murl&quot;:&quot;(.*?)&quot;', html)
    print(matches[:5])

scrape_bing_image('Chicken and Egg Curry')
